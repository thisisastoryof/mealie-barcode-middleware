import secrets

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApiToken


def hash_token(raw_token: str) -> str:
    return bcrypt.hashpw(raw_token.encode(), bcrypt.gensalt()).decode()


def verify_token(raw_token: str, token_hash: str) -> bool:
    return bcrypt.checkpw(raw_token.encode(), token_hash.encode())


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def require_token(request: Request, db: Session = Depends(get_db)) -> ApiToken:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    raw_token = auth_header.removeprefix("Bearer ").strip()
    return _authenticate_raw_token(raw_token, db)


def verify_psk(device_id: str, db: Session) -> ApiToken:
    """Authenticate using a pre-shared key (e.g. BinaryEye's deviceId field).

    Same token verification as Bearer auth, but the raw token comes from
    the request body instead of the Authorization header.
    """
    if not device_id or not device_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or empty device ID",
        )
    return _authenticate_raw_token(device_id.strip(), db)


def _authenticate_raw_token(raw_token: str, db: Session) -> ApiToken:
    """Core token verification logic shared by Bearer and PSK auth."""
    prefix = raw_token[:8]

    # Fast path: query by prefix (covers tokens created with prefix column)
    candidates = db.query(ApiToken).filter(ApiToken.token_prefix == prefix).all()
    for t in candidates:
        if verify_token(raw_token, t.token_hash):
            return t

    # Fallback: check tokens without prefix (legacy, pre-migration)
    legacy = db.query(ApiToken).filter(ApiToken.token_prefix.is_(None)).all()
    for t in legacy:
        if verify_token(raw_token, t.token_hash):
            # Backfill prefix for future lookups
            t.token_prefix = prefix
            db.commit()
            return t

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
    )
