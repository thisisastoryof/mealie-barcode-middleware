import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.applications import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.middleware import CSRFOriginMiddleware, SecurityHeadersMiddleware
from app.routers import barcodes, dashboard, items, health, notifications, scan, settings as settings_router
from app.services.scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    logger.info("Database initialized")

    # --- Lookup config validation ---
    upcdb_usable = settings.upcdb_enabled and bool(settings.upcdb_api_key)
    if settings.upcdb_enabled and not settings.upcdb_api_key:
        logger.warning(
            "UPCDB_ENABLED=True but UPCDB_API_KEY is not set — UPC Database will be skipped"
        )
    sources = []
    if settings.off_enabled:
        sources.append("OpenFoodFacts")
    if upcdb_usable:
        sources.append("UPCDatabase")
    if sources:
        primary = "OpenFoodFacts" if settings.lookup_primary == "off" else "UPCDatabase"
        if primary not in sources:
            primary = sources[0]
        logger.info(
            "Lookup: strategy=%s  primary=%s  sources=%s  background_enrich=%s",
            settings.lookup_strategy,
            primary,
            "+".join(sources),
            settings.lookup_enrich_in_background,
        )
    else:
        logger.warning("No barcode lookup sources enabled — scans will always be 'not_found'")

    if not settings.middleware_base_url:
        logger.info(
            "MIDDLEWARE_BASE_URL not set \u2014 notification action_url will use relative paths. "
            "Set MIDDLEWARE_BASE_URL=http://your-ip:9930 for full deep links in HA notifications."
        )
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(title="Barcode-Mealie Middleware", lifespan=lifespan)

# Security middleware (order matters: outermost runs first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFOriginMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include routers
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(scan.router, tags=["scan"])
app.include_router(health.router, tags=["health"])
app.include_router(barcodes.router, tags=["barcodes"])
app.include_router(items.router, tags=["items"])
app.include_router(notifications.router, tags=["notifications"])
app.include_router(settings_router.router, tags=["settings"])
