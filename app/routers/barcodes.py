import json
import logging

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import BarcodeCache, BarcodeFoodMapping, MealieFood, RetryQueue
from app.services.barcode_lookup import perform_lookup
from app.services.fuzzy import fuzzy_match

logger = logging.getLogger(__name__)
router = APIRouter()


def _templates():
    from app.main import templates
    return templates


@router.get("/barcodes", response_class=HTMLResponse)
def barcodes_list(
    request: Request,
    status: str = Query(default="all"),
    db: Session = Depends(get_db),
):
    query = db.query(BarcodeCache).order_by(BarcodeCache.created_at.desc())

    if status == "mapped":
        mapped_barcodes = db.query(BarcodeFoodMapping.barcode).subquery()
        query = query.filter(BarcodeCache.barcode.in_(mapped_barcodes))
    elif status == "pending":
        mapped_barcodes = db.query(BarcodeFoodMapping.barcode).subquery()
        query = query.filter(
            BarcodeCache.found == True,
            ~BarcodeCache.barcode.in_(mapped_barcodes),
        )
    elif status == "unknown":
        query = query.filter(BarcodeCache.found == False)

    barcodes = query.all()

    # Attach mapping info
    mappings = {m.barcode: m for m in db.query(BarcodeFoodMapping).all()}
    food_ids = [m.mealie_food_id for m in mappings.values()]
    foods = {f.id: f for f in db.query(MealieFood).filter(MealieFood.id.in_(food_ids)).all()} if food_ids else {}

    items = []
    for bc in barcodes:
        mapping = mappings.get(bc.barcode)
        food = foods.get(mapping.mealie_food_id) if mapping else None
        items.append({
            "barcode": bc,
            "mapping": mapping,
            "food": food,
        })

    return _templates().TemplateResponse(request, "barcodes.html", {
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
    mapping = db.get(BarcodeFoodMapping, barcode)
    mapped_food = db.get(MealieFood, mapping.mealie_food_id) if mapping else None

    # Get fuzzy candidates
    candidates = []
    if cached and cached.title:
        candidates = fuzzy_match(cached.title, cached.brand, db)[:10]

    # Find next unmapped barcode
    mapped_barcodes = [m.barcode for m in db.query(BarcodeFoodMapping).all()]
    next_unmapped = (
        db.query(BarcodeCache)
        .filter(BarcodeCache.found == True, ~BarcodeCache.barcode.in_(mapped_barcodes))
        .filter(BarcodeCache.barcode != barcode)
        .order_by(BarcodeCache.created_at.desc())
        .first()
    )

    return _templates().TemplateResponse(request, "barcode_detail.html", {
        "cached": cached,
        "mapping": mapping,
        "mapped_food": mapped_food,
        "candidates": candidates,
        "next_unmapped": next_unmapped,
        "threshold": settings.fuzzy_match_threshold,
    })


@router.post("/barcodes/{barcode}/map")
def barcode_map(
    barcode: str,
    food_id: str = Form(...),
    db: Session = Depends(get_db),
):
    existing = db.get(BarcodeFoodMapping, barcode)
    if existing:
        existing.mealie_food_id = food_id
        existing.mapped_by = "manual"
    else:
        db.add(BarcodeFoodMapping(barcode=barcode, mealie_food_id=food_id, mapped_by="manual"))
    db.commit()
    return RedirectResponse(f"/barcodes/{barcode}", status_code=303)


@router.post("/barcodes/{barcode}/unmap")
def barcode_unmap(barcode: str, db: Session = Depends(get_db)):
    existing = db.get(BarcodeFoodMapping, barcode)
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
    mapping = db.get(BarcodeFoodMapping, barcode)
    if mapping:
        db.delete(mapping)
    cached = db.get(BarcodeCache, barcode)
    if cached:
        db.delete(cached)
    db.commit()
    return RedirectResponse("/barcodes", status_code=303)


@router.get("/barcodes-search")
def barcodes_search(q: str = Query(default=""), db: Session = Depends(get_db)):
    """AJAX endpoint for food search on barcode detail page."""
    if not q.strip():
        return []
    foods = (
        db.query(MealieFood)
        .filter(MealieFood.name.ilike(f"%{q}%"))
        .limit(20)
        .all()
    )
    return [{"id": f.id, "name": f.name} for f in foods]
