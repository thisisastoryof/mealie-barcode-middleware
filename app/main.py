import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.applications import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.middleware import CSRFOriginMiddleware, LoginRequiredMiddleware, RememberMeSessionMiddleware, SecurityHeadersMiddleware, get_session_secret
from app.routers import barcodes, dashboard, docs, items, health, labels, login, notifications, scan, settings as settings_router
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

    # Load DB setting overrides (must come after init_db creates the table)
    settings.load_overrides_from_db()

    # Load theme settings into the template cache
    from app.database import SessionLocal
    from app.theme import get_theme
    from app.templating import set_cached_theme
    db = SessionLocal()
    try:
        set_cached_theme(get_theme(db))
    finally:
        db.close()

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


app = FastAPI(title="Mealie Barcode Middleware", lifespan=lifespan, docs_url="/api/docs", redoc_url="/api/redoc")

# Security middleware (order matters: outermost runs first, last added = outermost)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFOriginMiddleware)
app.add_middleware(LoginRequiredMiddleware)
app.add_middleware(RememberMeSessionMiddleware, secret_key=get_session_secret(), max_age=settings.session_max_age_days * 24 * 3600)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include routers
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(docs.router, tags=["docs"])
app.include_router(scan.router, tags=["scan"])
app.include_router(health.router, tags=["health"])
app.include_router(login.router, tags=["auth"])
app.include_router(barcodes.router, tags=["barcodes"])
app.include_router(items.router, tags=["items"])
app.include_router(labels.router, tags=["labels"])
app.include_router(notifications.router, tags=["notifications"])
app.include_router(settings_router.router, tags=["settings"])
