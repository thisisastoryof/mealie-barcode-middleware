import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BarcodeFoodMapping, BarcodeCache, MealieFood
from app.services.mealie import sync_foods

logger = logging.getLogger(__name__)
router = APIRouter()


def _templates():
    from app.main import templates
    return templates


@router.get("/foods", response_class=HTMLResponse)
def foods_list(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    query = db.query(MealieFood)
    if q:
        query = query.filter(MealieFood.name.ilike(f"%{q}%") | MealieFood.aliases.ilike(f"%{q}%"))
    foods = query.order_by(func.lower(MealieFood.name)).all()

    # Count mappings per food
    mapping_counts = {}
    for mapping in db.query(BarcodeFoodMapping).all():
        mapping_counts[mapping.mealie_food_id] = mapping_counts.get(mapping.mealie_food_id, 0) + 1

    items = [{"food": f, "mapping_count": mapping_counts.get(f.id, 0)} for f in foods]

    return _templates().TemplateResponse(request, "foods.html", {
        "items": items,
        "search_query": q,
    })


@router.get("/foods/{food_id}", response_class=HTMLResponse)
def food_detail(request: Request, food_id: str, db: Session = Depends(get_db)):
    food = db.get(MealieFood, food_id)
    if not food:
        return HTMLResponse("Food not found", status_code=404)

    # Get all barcodes mapped to this food
    mappings = db.query(BarcodeFoodMapping).filter(BarcodeFoodMapping.mealie_food_id == food_id).all()
    barcode_ids = [m.barcode for m in mappings]
    barcodes = db.query(BarcodeCache).filter(BarcodeCache.barcode.in_(barcode_ids)).all() if barcode_ids else []

    barcode_map = {bc.barcode: bc for bc in barcodes}
    mapped_items = []
    for m in mappings:
        bc = barcode_map.get(m.barcode)
        mapped_items.append({"mapping": m, "barcode": bc})

    return _templates().TemplateResponse(request, "food_detail.html", {
        "food": food,
        "mapped_items": mapped_items,
    })


@router.post("/foods/{food_id}/remove-mapping/{barcode}")
def remove_food_mapping(food_id: str, barcode: str, db: Session = Depends(get_db)):
    mapping = db.get(BarcodeFoodMapping, barcode)
    if mapping and mapping.mealie_food_id == food_id:
        db.delete(mapping)
        db.commit()
    return RedirectResponse(f"/foods/{food_id}", status_code=303)


@router.post("/foods/sync")
def trigger_food_sync(db: Session = Depends(get_db)):
    try:
        sync_foods(db)
    except Exception as e:
        logger.error(f"Manual food sync failed: {e}")
    return RedirectResponse("/foods", status_code=303)
