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


@router.get("/labels/fuzzy")
def labels_fuzzy_match(q: str = Query(default=""), db: Session = Depends(get_db)):
    """Fuzzy-match free text against items. Read-only, no mutations."""
    q = q.strip()
    if not q:
        return {"candidates": []}
    candidates = fuzzy_match(q, None, db)
    top = [c for c in candidates[:5] if c["score"] >= 60]
    return {
        "candidates": [{"id": c["item_id"], "name": c["item_name"], "score": c["score"]} for c in top],
    }


@router.post("/labels/register", response_class=JSONResponse)
async def register_labels_batch(request: Request, db: Session = Depends(get_db)):
    """Batch-register labels at print time.

    Body JSON: { "labels": [{"text": "Milk", "item_id": "uuid-or-null"}, ...] }
    Creates BarcodeCache for all; creates BarcodeMapping only when item_id is set.
    """
    body = await request.json()
    labels = body.get("labels", [])

    if not labels:
        return JSONResponse({"error": "labels array is required"}, status_code=400)

    registered = 0
    mapped = 0

    for entry in labels:
        text = entry.get("text", "").strip()
        item_id = entry.get("item_id")
        if not text:
            continue

        barcode = f"GENERIC:{text}"

        # Upsert barcode_cache
        existing_cache = db.get(BarcodeCache, barcode)
        if not existing_cache:
            db.add(BarcodeCache(
                barcode=barcode,
                source="generic",
                title=text,
                found=True,
                lookup_attempted_at=utcnow(),
            ))
            registered += 1

        # Create mapping only if item_id provided and valid
        if item_id:
            item = db.get(Item, item_id)
            if item:
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
                mapped += 1

    db.commit()
    return {"registered": registered, "mapped": mapped, "total": len(labels)}
