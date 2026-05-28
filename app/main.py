import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.applications import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.config import settings
from app.database import get_db, init_db
from app.events import scan_events
from app.models import BarcodeCache, BarcodeFoodMapping, RetryQueue
from app.routers import barcodes, foods, health, notifications, scan, settings as settings_router
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

_tz = ZoneInfo(settings.timezone)


def _localtime(value, fmt="%Y-%m-%d %H:%M"):
    """Jinja2 filter: convert a UTC datetime to the configured local timezone."""
    if not value:
        return "\u2014"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_tz).strftime(fmt)


templates.env.filters["localtime"] = _localtime


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
app.include_router(notifications.router, tags=["notifications"])
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

    return templates.TemplateResponse(request, "dashboard.html", {
        "total_barcodes": total_barcodes,
        "mapped_count": mapped_count,
        "pending_count": pending_count,
        "queue_depth": queue_depth,
        "unknown_count": unknown_count,
        "recent_items": recent_items,
        "mealie_reachable": mealie_reachable,
        "last_sync_time": last_sync_time,
    })


@app.get("/api/dashboard")
def dashboard_api(db: Session = Depends(get_db)):
    """JSON endpoint for partial dashboard refresh."""
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

    recent = db.query(BarcodeCache).order_by(BarcodeCache.created_at.desc()).limit(10).all()
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
        recent_items.append({
            "barcode": bc.barcode,
            "title": bc.title or "\u2014",
            "source": bc.source or "\u2014",
            "status": status,
            "created_at": _localtime(bc.created_at),
        })

    return {
        "total_barcodes": total_barcodes,
        "mapped_count": mapped_count,
        "pending_count": pending_count,
        "queue_depth": queue_depth,
        "recent_items": recent_items,
    }


@app.get("/events")
async def sse_stream():
    """Server-Sent Events stream for real-time scan notifications."""
    queue = scan_events.subscribe()

    async def _generate():
        try:
            while True:
                msg = await queue.get()
                yield msg
        except asyncio.CancelledError:
            pass
        finally:
            scan_events.unsubscribe(queue)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
