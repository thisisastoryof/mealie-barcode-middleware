import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.database import get_db
from app.events import scan_events
from app.models import ApiToken, BarcodeCache, BarcodeMapping, Item, RetryQueue
from app.services.mealie import check_connectivity
from app.templating import templates, _localtime

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
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

    has_tokens = db.query(ApiToken).first() is not None

    return templates.TemplateResponse(request, "dashboard.html", {
        "total_barcodes": total_barcodes,
        "mapped_count": mapped_count,
        "pending_count": pending_count,
        "queue_depth": queue_depth,
        "unknown_count": unknown_count,
        "recent_items": recent_items,
        "mealie_reachable": mealie_reachable,
        "last_sync_time": last_sync_time,
        "has_tokens": has_tokens,
    })


@router.get("/api/dashboard")
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
            "item_name": item.name if item else None,
            "item_id": item.id if item else None,
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


@router.get("/events")
async def sse_stream():
    """Server-Sent Events stream for real-time scan notifications."""
    queue = scan_events.subscribe()

    async def _generate():
        try:
            # Send initial comment to confirm connection
            yield ": connected\n\n"
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
