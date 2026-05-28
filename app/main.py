import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.applications import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.models import BarcodeCache, BarcodeFoodMapping, RetryQueue
from app.routers import barcodes, foods, health, scan, settings as settings_router
from app.services.mealie import check_connectivity
from app.services.scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    logger.info("Database initialized")
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(title="Barcode-Mealie Middleware", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include routers
app.include_router(scan.router, tags=["scan"])
app.include_router(health.router, tags=["health"])
app.include_router(barcodes.router, tags=["barcodes"])
app.include_router(foods.router, tags=["foods"])
app.include_router(settings_router.router, tags=["settings"])


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    # Stats
    total_barcodes = db.query(BarcodeCache).count()
    mapped_count = db.query(BarcodeFoodMapping).count()
    pending_count = (
        db.query(BarcodeCache)
        .filter(BarcodeCache.found == True)
        .filter(~BarcodeCache.barcode.in_(
            db.query(BarcodeFoodMapping.barcode)
        ))
        .count()
    )
    queue_depth = db.query(RetryQueue).count()
    unknown_count = db.query(BarcodeCache).filter(BarcodeCache.found == False).count()

    # Recent scans
    recent = db.query(BarcodeCache).order_by(BarcodeCache.created_at.desc()).limit(10).all()

    # Build recent items with status
    mappings = {m.barcode: m for m in db.query(BarcodeFoodMapping).all()}
    queued_barcodes = set(r.barcode for r in db.query(RetryQueue).all())

    recent_items = []
    for bc in recent:
        if bc.barcode in mappings:
            status = "mapped"
        elif bc.barcode in queued_barcodes:
            status = "queued"
        elif not bc.found:
            status = "unknown"
        else:
            status = "pending"
        recent_items.append({"barcode": bc, "status": status})

    # Health
    mealie_reachable = check_connectivity()

    from app.models import MealieFood
    last_sync = db.query(MealieFood.synced_at).order_by(MealieFood.synced_at.desc()).first()
    last_sync_time = last_sync[0] if last_sync else None

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_barcodes": total_barcodes,
        "mapped_count": mapped_count,
        "pending_count": pending_count,
        "queue_depth": queue_depth,
        "unknown_count": unknown_count,
        "recent_items": recent_items,
        "mealie_reachable": mealie_reachable,
        "last_sync_time": last_sync_time,
    })
