"""Security middleware — headers and CSRF origin check."""

import logging
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Safe (read-only) HTTP methods that don't need CSRF protection
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Paths exempt from CSRF check (token-authenticated API)
_CSRF_EXEMPT_PREFIXES = ("/scan",)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-eval'; "
            "style-src 'self'; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "img-src 'self' data:"
        )

        return response


class CSRFOriginMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection via Origin/Referer header validation.

    On state-changing requests (POST, PUT, DELETE, PATCH), verify that
    the Origin or Referer header matches the request's host. Rejects
    cross-origin form submissions from attacker sites.

    Exempt: token-authenticated endpoints (/scan).
    """

    async def dispatch(self, request: Request, call_next):
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        # Skip CSRF check for token-authenticated API endpoints
        path = request.url.path
        for prefix in _CSRF_EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Determine expected host
        expected_host = request.headers.get("host", "")

        # Check Origin header first (most reliable)
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.netloc == expected_host:
                return await call_next(request)
            logger.warning(f"CSRF blocked: origin '{origin}' != host '{expected_host}' on {path}")
            return Response("Forbidden — origin mismatch", status_code=403)

        # Fall back to Referer header
        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            if parsed.netloc == expected_host:
                return await call_next(request)
            logger.warning(f"CSRF blocked: referer '{referer}' != host '{expected_host}' on {path}")
            return Response("Forbidden — referer mismatch", status_code=403)

        # No Origin or Referer — block (strict mode)
        # Browsers always send Origin on POST from forms and fetch.
        # Missing headers typically means non-browser client or privacy stripping.
        logger.warning(f"CSRF blocked: no origin/referer on {request.method} {path}")
        return Response("Forbidden — missing origin", status_code=403)
