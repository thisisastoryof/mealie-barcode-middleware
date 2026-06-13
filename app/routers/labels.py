import io
import logging

import segno
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BarcodeCache, BarcodeMapping, Item
from app.services.fuzzy import fuzzy_match
from app.templating import templates
from app.utils import utcnow

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/labels", response_class=HTMLResponse)
def labels_page(request: Request):
    return templates.TemplateResponse(request, "labels.html", {})


@router.get("/labels/qr.svg")
def generate_qr_svg(text: str = Query(..., min_length=1)):
    """Generate a QR code SVG for GENERIC:{text}."""
    content = f"GENERIC:{text}"
    qr = segno.make(content, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=4, border=2, xmldecl=False)
    return Response(content=buf.getvalue(), media_type="image/svg+xml")


@router.get("/labels/search")
def labels_search_items(q: str = Query(default=""), db: Session = Depends(get_db)):
    """Search items for the label autocomplete."""
    q = q.strip()
    if not q:
        return []
    words = [w for w in q.split() if len(w) >= 2]
    if not words:
        words = [q]
    conditions = [Item.name.ilike(f"%{word}%") for word in words]
    items = db.query(Item).filter(or_(*conditions)).order_by(Item.name).limit(20).all()
    return [{"id": i.id, "name": i.name, "source": i.source} for i in items]


@router.post("/labels/register", response_class=JSONResponse)
async def register_label(request: Request, db: Session = Depends(get_db)):
    """Pre-register a GENERIC barcode mapping.

    Body JSON: { "text": "Milk", "item_id": "optional-item-id" }
    - If item_id is provided: directly map to that item.
    - If item_id is absent: run fuzzy matching and return candidates.
    """
    body = await request.json()
    text = body.get("text", "").strip()
    item_id = body.get("item_id")

    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)

    barcode = f"GENERIC:{text}"

    # Ensure barcode_cache entry exists
    existing_cache = db.get(BarcodeCache, barcode)
    if not existing_cache:
        cache_entry = BarcodeCache(
            barcode=barcode,
            source="generic",
            title=text,
            found=True,
            lookup_attempted_at=utcnow(),
        )
        db.add(cache_entry)
        db.flush()

    # If item_id provided, directly create/update mapping
    if item_id:
        item = db.get(Item, item_id)
        if not item:
            return JSONResponse({"error": "item not found"}, status_code=404)

        existing_mapping = db.get(BarcodeMapping, barcode)
        if existing_mapping:
            existing_mapping.item_id = item_id
            existing_mapping.mapped_by = "manual"
        else:
            db.add(BarcodeMapping(
                barcode=barcode,
                item_id=item_id,
                mapped_by="manual",
            ))
        db.commit()
        return {"status": "mapped", "item_name": item.name, "item_id": item.id}

    # No item_id — run fuzzy matching and return top candidates
    candidates = fuzzy_match(text, None, db)
    top = [c for c in candidates[:5] if c["score"] >= 60]

    if top:
        return {
            "status": "candidates",
            "candidates": [{"id": c["item_id"], "name": c["item_name"], "score": c["score"]} for c in top],
        }

    # No match — just confirm the cache entry exists (it does from above)
    db.commit()
    return {"status": "no_match", "message": f"No matching item. '{text}' will be added as a note when scanned."}
