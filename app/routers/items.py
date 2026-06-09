import logging

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BarcodeCache, BarcodeMapping, Item
from app.services.mealie import sync_items
from app.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/items", response_class=HTMLResponse)
def items_list(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    query = db.query(Item)
    if q:
        query = query.filter(Item.name.ilike(f"%{q}%") | Item.aliases.ilike(f"%{q}%"))
    all_items = query.order_by(func.lower(Item.name)).all()

    # Count mappings per item
    mapping_counts = {}
    for mapping in db.query(BarcodeMapping).all():
        mapping_counts[mapping.item_id] = mapping_counts.get(mapping.item_id, 0) + 1

    items = [{"item": i, "mapping_count": mapping_counts.get(i.id, 0)} for i in all_items]

    last_synced = next((i.synced_at for i in all_items if i.source == "mealie" and i.synced_at), None)

    return templates.TemplateResponse(request, "items.html", {
        "items": items,
        "search_query": q,
        "last_synced": last_synced,
    })


@router.get("/items/{item_id}", response_class=HTMLResponse)
def item_detail(request: Request, item_id: str, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if not item:
        return templates.TemplateResponse(request, "404.html", {"message": "Item not found"}, status_code=404)

    # Get all barcodes mapped to this item
    mappings = db.query(BarcodeMapping).filter(BarcodeMapping.item_id == item_id).all()
    barcode_ids = [m.barcode for m in mappings]
    barcodes = db.query(BarcodeCache).filter(BarcodeCache.barcode.in_(barcode_ids)).all() if barcode_ids else []

    barcode_map = {bc.barcode: bc for bc in barcodes}
    mapped_items = []
    for m in mappings:
        bc = barcode_map.get(m.barcode)
        mapped_items.append({"mapping": m, "barcode": bc})

    return templates.TemplateResponse(request, "item_detail.html", {
        "item": item,
        "mapped_items": mapped_items,
    })


@router.post("/items/{item_id}/remove-mapping/{barcode}")
def remove_item_mapping(item_id: str, barcode: str, db: Session = Depends(get_db)):
    mapping = db.get(BarcodeMapping, barcode)
    if mapping and mapping.item_id == item_id:
        db.delete(mapping)
        db.commit()
    return RedirectResponse(f"/items/{item_id}", status_code=303)


@router.post("/items/sync")
def trigger_sync(db: Session = Depends(get_db)):
    try:
        sync_items(db)
    except Exception as e:
        logger.error(f"Manual item sync failed: {e}")
    return RedirectResponse("/items", status_code=303)


@router.post("/items/add")
def add_custom_item(name: str = Form(...), db: Session = Depends(get_db)):
    """Create a manual item (non-Mealie)."""
    name = name.strip()
    if not name:
        return RedirectResponse("/items", status_code=303)
    db.add(Item(name=name, source="manual"))
    db.commit()
    return RedirectResponse("/items", status_code=303)


@router.post("/items/{item_id}/delete")
def delete_custom_item(item_id: str, db: Session = Depends(get_db)):
    """Delete a manual item. Mealie items cannot be deleted."""
    item = db.get(Item, item_id)
    if not item or item.source != "manual":
        return RedirectResponse("/items", status_code=303)
    # Remove any barcode mappings pointing to this item
    db.query(BarcodeMapping).filter(BarcodeMapping.item_id == item_id).delete()
    db.delete(item)
    db.commit()
    return RedirectResponse("/items", status_code=303)
