import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, Request
from fastapi.applications import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.config import settings
from app.database import get_db, init_db
from app.events import scan_events
from app.models import BarcodeCache, BarcodeMapping, Item, RetryQueue
from app.routers import barcodes, items, health, notifications, scan, settings as settings_router
from app.services.mealie import check_connectivity
from app.services.scheduler import start_scheduler, stop_scheduler
from app.templating import templates, _localtime

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
app.include_router(items.router, tags=["items"])
app.include_router(notifications.router, tags=["notifications"])
app.include_router(settings_router.router, tags=["settings"])


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    # Stats
    total_barcodes = db.query(BarcodeCache).count()
    mapped_count = db.query(BarcodeMapping).count()
    pending_count = (
        db.query(BarcodeCache)
        .filter(BarcodeCache.found == True)
        .filter(~BarcodeCache.barcode.in_(
            db.query(BarcodeMapping.barcode)
        ))
        .count()
    )
    queue_depth = db.query(RetryQueue).count()
    unknown_count = db.query(BarcodeCache).filter(BarcodeCache.found == False).count()

    # Recent scans
    recent = db.query(BarcodeCache).order_by(BarcodeCache.created_at.desc()).limit(10).all()

    # Build recent items with status
    mappings = {m.barcode: m for m in db.query(BarcodeMapping).all()}
    queued_barcodes = set(r.barcode for r in db.query(RetryQueue).all())
    item_ids = [m.item_id for m in mappings.values()]
    items_map = {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}

    recent_items = []
    for bc in recent:
        if bc.barcode in mappings:
            status = "mapped"
            mapping = mappings[bc.barcode]
            item = items_map.get(mapping.item_id)
        else:
            item = None
            if bc.barcode in queued_barcodes:
                status = "queued"
            elif not bc.found:
                status = "unknown"
            else:
                status = "pending"
        recent_items.append({"barcode": bc, "status": status, "item": item})

    # Health
    mealie_reachable = check_connectivity()

    last_sync = db.query(Item.synced_at).filter(Item.source == "mealie").order_by(Item.synced_at.desc()).first()
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


@app.get("/api/barcodes")
def barcodes_api(status: str = "all", db: Session = Depends(get_db)):
    """JSON endpoint for live-refreshing the barcodes table."""
    from sqlalchemy import func

    query = db.query(BarcodeCache).order_by(BarcodeCache.created_at.desc())

    if status == "mapped":
        mapped_sub = db.query(BarcodeMapping.barcode).subquery()
        query = query.filter(BarcodeCache.barcode.in_(mapped_sub))
    elif status == "pending":
        mapped_sub = db.query(BarcodeMapping.barcode).subquery()
        query = query.filter(
            BarcodeCache.found == True,
            ~BarcodeCache.barcode.in_(mapped_sub),
        )
    elif status == "unknown":
        query = query.filter(BarcodeCache.found == False)

    barcodes_list = query.limit(200).all()

    mappings = {m.barcode: m for m in db.query(BarcodeMapping).all()}
    item_ids = [m.item_id for m in mappings.values()]
    items_map = (
        {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()}
        if item_ids else {}
    )

    items = []
    for bc in barcodes_list:
        mapping = mappings.get(bc.barcode)
        item = items_map.get(mapping.item_id) if mapping else None
        items.append({
            "barcode": bc.barcode,
            "title": bc.title or "\u2014",
            "brand": bc.brand or "\u2014",
            "source": bc.source or "\u2014",
            "food_name": item.name if item else None,
            "food_id": item.id if item else None,
            "mapped_by": mapping.mapped_by if mapping else None,
            "created_at": _localtime(bc.created_at),
        })

    return {"items": items}


@app.get("/api/dashboard")
def dashboard_api(db: Session = Depends(get_db)):
    """JSON endpoint for partial dashboard refresh."""
    total_barcodes = db.query(BarcodeCache).count()
    mapped_count = db.query(BarcodeMapping).count()
    pending_count = (
        db.query(BarcodeCache)
        .filter(BarcodeCache.found == True)
        .filter(~BarcodeCache.barcode.in_(
            db.query(BarcodeMapping.barcode)
        ))
        .count()
    )
    queue_depth = db.query(RetryQueue).count()

    recent = db.query(BarcodeCache).order_by(BarcodeCache.created_at.desc()).limit(10).all()
    mappings = {m.barcode: m for m in db.query(BarcodeMapping).all()}
    queued_barcodes = set(r.barcode for r in db.query(RetryQueue).all())
    item_ids = [m.item_id for m in mappings.values()]
    items_map = {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}

    recent_items = []
    for bc in recent:
        if bc.barcode in mappings:
            status = "mapped"
            mapping = mappings[bc.barcode]
            item = items_map.get(mapping.item_id)
        else:
            item = None
            if bc.barcode in queued_barcodes:
                status = "queued"
            elif not bc.found:
                status = "unknown"
            else:
                status = "pending"
        recent_items.append({
            "barcode": bc.barcode,
            "food_name": item.name if item else None,
            "food_id": item.id if item else None,
            "title": bc.title or "\u2014",
            "source": bc.source or "\u2014",
            "status": status,
            "created_at": _localtime(bc.created_at),
        })

    unknown_count = db.query(BarcodeCache).filter(BarcodeCache.found == False).count()

    return {
        "total_barcodes": total_barcodes,
        "mapped_count": mapped_count,
        "pending_count": pending_count,
        "queue_depth": queue_depth,
        "unknown_count": unknown_count,
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
