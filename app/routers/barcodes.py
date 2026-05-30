import json
import logging

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import BarcodeCache, BarcodeMapping, Item, Notification, RetryQueue
from app.services.barcode_lookup import perform_lookup
from app.services.fuzzy import fuzzy_match
from app.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/barcodes", response_class=HTMLResponse)
def barcodes_list(
    request: Request,
    status: str = Query(default="all"),
    db: Session = Depends(get_db),
):
    query = db.query(BarcodeCache).order_by(BarcodeCache.created_at.desc())

    if status == "mapped":
        mapped_barcodes = db.query(BarcodeMapping.barcode).subquery()
        query = query.filter(BarcodeCache.barcode.in_(mapped_barcodes))
    elif status == "pending":
        mapped_barcodes = db.query(BarcodeMapping.barcode).subquery()
        query = query.filter(
            BarcodeCache.found == True,
            ~BarcodeCache.barcode.in_(mapped_barcodes),
        )
    elif status == "unknown":
        query = query.filter(BarcodeCache.found == False)

    barcodes = query.all()

    # Attach mapping info and compute status
    mappings = {m.barcode: m for m in db.query(BarcodeMapping).all()}
    queued_barcodes = set(r.barcode for r in db.query(RetryQueue).all())
    item_ids = [m.item_id for m in mappings.values()]
    items_map = {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}

    items = []
    for bc in barcodes:
        mapping = mappings.get(bc.barcode)
        item = items_map.get(mapping.item_id) if mapping else None
        if mapping:
            bc_status = "mapped"
        elif bc.barcode in queued_barcodes:
            bc_status = "queued"
        elif not bc.found:
            bc_status = "unknown"
        else:
            bc_status = "pending"
        items.append({
            "barcode": bc,
            "mapping": mapping,
            "item": item,
            "status": bc_status,
        })

    return templates.TemplateResponse(request, "barcodes.html", {
        "items": items,
        "current_status": status,
    })


@router.get("/barcodes/{barcode}", response_class=HTMLResponse)
def barcode_detail(
    request: Request,
    barcode: str,
    db: Session = Depends(get_db),
):
    cached = db.get(BarcodeCache, barcode)
    mapping = db.get(BarcodeMapping, barcode)
    mapped_item = db.get(Item, mapping.item_id) if mapping else None

    # Auto-clear notifications for this barcode on visit
    db.query(Notification).filter(
        Notification.barcode == barcode,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()

    # Get fuzzy candidates
    candidates = []
    if cached and cached.title:
        candidates = fuzzy_match(cached.title, cached.brand, db)[:10]

    # Find next unmapped barcode
    mapped_barcodes = [m.barcode for m in db.query(BarcodeMapping).all()]
    next_unmapped = (
        db.query(BarcodeCache)
        .filter(BarcodeCache.found == True, ~BarcodeCache.barcode.in_(mapped_barcodes))
        .filter(BarcodeCache.barcode != barcode)
        .order_by(BarcodeCache.created_at.desc())
        .first()
    )

    return templates.TemplateResponse(request, "barcode_detail.html", {
        "cached": cached,
        "mapping": mapping,
        "mapped_item": mapped_item,
        "candidates": candidates,
        "next_unmapped": next_unmapped,
        "threshold": settings.fuzzy_match_threshold,
    })


@router.post("/barcodes/{barcode}/map")
def barcode_map(
    barcode: str,
    item_id: str = Form(...),
    db: Session = Depends(get_db),
):
    existing = db.get(BarcodeMapping, barcode)
    if existing:
        existing.item_id = item_id
        existing.mapped_by = "manual"
    else:
        db.add(BarcodeMapping(barcode=barcode, item_id=item_id, mapped_by="manual"))

    # Mark notifications for this barcode as read
    db.query(Notification).filter(
        Notification.barcode == barcode,
        Notification.is_read == False,
    ).update({"is_read": True})

    db.commit()
    return RedirectResponse(f"/barcodes/{barcode}", status_code=303)


@router.post("/barcodes/{barcode}/create-and-map")
def barcode_create_and_map(
    barcode: str,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    """Create a new manual item and map this barcode to it in one step."""
    name = name.strip()
    if not name:
        return RedirectResponse(f"/barcodes/{barcode}", status_code=303)

    item = Item(name=name, source="manual")
    db.add(item)
    db.flush()  # get the generated id

    existing = db.get(BarcodeMapping, barcode)
    if existing:
        existing.item_id = item.id
        existing.mapped_by = "manual"
    else:
        db.add(BarcodeMapping(barcode=barcode, item_id=item.id, mapped_by="manual"))

    # Mark notifications for this barcode as read
    db.query(Notification).filter(
        Notification.barcode == barcode,
        Notification.is_read == False,
    ).update({"is_read": True})

    db.commit()
    return RedirectResponse(f"/barcodes/{barcode}", status_code=303)


@router.post("/barcodes/{barcode}/unmap")
def barcode_unmap(barcode: str, db: Session = Depends(get_db)):
    existing = db.get(BarcodeMapping, barcode)
    if existing:
        db.delete(existing)
        db.commit()
    return RedirectResponse(f"/barcodes/{barcode}", status_code=303)


@router.post("/barcodes/{barcode}/retry-lookup")
def barcode_retry_lookup(barcode: str, db: Session = Depends(get_db)):
    perform_lookup(barcode, db)
    return RedirectResponse(f"/barcodes/{barcode}", status_code=303)


@router.post("/barcodes/{barcode}/delete")
def barcode_delete(barcode: str, db: Session = Depends(get_db)):
    """Delete cached barcode and its mapping."""
    db.query(RetryQueue).filter(RetryQueue.barcode == barcode).delete()
    mapping = db.get(BarcodeMapping, barcode)
    if mapping:
        db.delete(mapping)
    cached = db.get(BarcodeCache, barcode)
    if cached:
        db.delete(cached)
    db.commit()
    return RedirectResponse("/barcodes", status_code=303)


@router.get("/barcodes-search")
def barcodes_search(q: str = Query(default=""), db: Session = Depends(get_db)):
    """AJAX endpoint for item search on barcode detail page."""
    q = q.strip()
    if not q:
        return []
    # Split query into words, match items containing ANY word
    words = [w for w in q.split() if len(w) >= 2]
    if not words:
        words = [q]
    conditions = [Item.name.ilike(f"%{word}%") for word in words]
    items = db.query(Item).filter(or_(*conditions)).limit(20).all()
    return [{"id": i.id, "name": i.name, "source": i.source} for i in items]


@router.get("/api/barcodes")
def barcodes_api(status: str = "all", db: Session = Depends(get_db)):
    """JSON endpoint for live-refreshing the barcodes table."""
    from app.templating import _localtime

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
    queued_barcodes = set(r.barcode for r in db.query(RetryQueue).all())
    item_ids = [m.item_id for m in mappings.values()]
    items_map = (
        {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()}
        if item_ids else {}
    )

    result_items = []
    for bc in barcodes_list:
        mapping = mappings.get(bc.barcode)
        item = items_map.get(mapping.item_id) if mapping else None
        if mapping:
            bc_status = "mapped"
        elif bc.barcode in queued_barcodes:
            bc_status = "queued"
        elif not bc.found:
            bc_status = "unknown"
        else:
            bc_status = "pending"
        result_items.append({
            "barcode": bc.barcode,
            "title": bc.title or "\u2014",
            "brand": bc.brand or "\u2014",
            "source": bc.source or "\u2014",
            "status": bc_status,
            "food_name": item.name if item else None,
            "food_id": item.id if item else None,
            "mapped_by": mapping.mapped_by if mapping else None,
            "created_at": _localtime(bc.created_at),
        })

    return {"items": result_items}
