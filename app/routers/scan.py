import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_token
from app.config import settings
from app.database import get_db
from app.events import scan_events
from app.models import BarcodeCache, BarcodeFoodMapping, MealieFood, Notification
from app.services.barcode_lookup import perform_lookup
from app.services.fuzzy import try_auto_map
from app.services.mealie import (
    add_to_shopping_list_by_food,
    add_to_shopping_list_by_note,
    enqueue_retry,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)
router = APIRouter()


class ScanRequest(BaseModel):
    barcode: str


class ScanResponse(BaseModel):
    result: str  # added | added_as_note | queued | unknown
    food: str | None = None
    via: str | None = None  # food_id | note


@router.post("/scan", response_model=ScanResponse)
def scan_barcode(
    body: ScanRequest,
    _token=Depends(require_token),
    db: Session = Depends(get_db),
):
    barcode = body.barcode.strip()
    if not barcode:
        return ScanResponse(result="unknown", food=None, via=None)

    # --- GENERIC QR code handling ---
    if barcode.upper().startswith("GENERIC:"):
        term = barcode[len("GENERIC:"):].strip()
        resp = _handle_generic(term, barcode, db)
        _emit_scan_event(barcode, resp)
        return resp

    # --- Standard barcode flow ---
    # Step 1: Check existing mapping
    mapping = db.get(BarcodeFoodMapping, barcode)
    if mapping:
        food = db.get(MealieFood, mapping.mealie_food_id)
        food_name = food.name if food else barcode
        resp = _add_via_food_id(mapping.mealie_food_id, food_name, barcode, db)
        _emit_scan_event(barcode, resp)
        return resp

    # Step 2: Check cache / perform lookup
    cached = db.get(BarcodeCache, barcode)
    needs_lookup = False

    if cached is None:
        needs_lookup = True
    elif not cached.found:
        # Check TTL
        if cached.lookup_attempted_at:
            ttl_expiry = cached.lookup_attempted_at + timedelta(days=settings.lookup_ttl_days)
            if utcnow() > ttl_expiry:
                needs_lookup = True

    if needs_lookup:
        cached = perform_lookup(barcode, db)

    if not cached.found:
        # Not found anywhere — add as note with barcode string
        note = barcode
        success = add_to_shopping_list_by_note(note)
        if success:
            resp = ScanResponse(result="unknown", food=None, via=None)
        else:
            _enqueue_note(barcode, note, db)
            resp = ScanResponse(result="unknown", food=None, via=None)
        _emit_scan_event(barcode, resp)
        _save_notification(barcode, "Unknown barcode", f"Not found in any product database", "unknown", db)
        return resp

    # Step 3: Attempt fuzzy auto-mapping
    food_id = try_auto_map(barcode, cached.title or barcode, cached.brand, db)
    if food_id:
        food = db.get(MealieFood, food_id)
        food_name = food.name if food else cached.title or barcode
        resp = _add_via_food_id(food_id, food_name, barcode, db)
        _emit_scan_event(barcode, resp)
        _save_notification(barcode, "Auto-mapped — confirm?", f"{cached.title or barcode} → {food_name}", "auto_mapped", db)
        return resp

    # No mapping — add as note with product title
    note = cached.title or barcode
    success = add_to_shopping_list_by_note(note)
    if success:
        resp = ScanResponse(result="added_as_note", food=note, via="note")
    else:
        _enqueue_note(barcode, note, db)
        resp = ScanResponse(result="queued", food=note, via="note")
    _emit_scan_event(barcode, resp)
    _save_notification(barcode, "Mapping needed", f"{note} — assign to a Mealie food", "needs_mapping", db)
    return resp


def _emit_scan_event(barcode: str, resp: ScanResponse):
    """Publish a scan event to all SSE listeners (live alerts only)."""
    scan_events.publish("scan", {
        "barcode": barcode,
        "result": resp.result,
        "food": resp.food,
    })


def _save_notification(barcode: str, title: str, message: str, result: str, db: Session):
    """Persist an actionable notification for the bell dropdown (deduplicated)."""
    existing = (
        db.query(Notification)
        .filter(Notification.barcode == barcode, Notification.is_read == False)
        .first()
    )
    if existing:
        return
    db.add(Notification(
        barcode=barcode,
        title=title,
        message=message,
        result=result,
    ))
    db.commit()


def _handle_generic(term: str, barcode: str, db: Session) -> ScanResponse:
    """Handle GENERIC: prefixed scans — fuzzy search mealie_foods."""
    from rapidfuzz import fuzz

    if not term:
        return ScanResponse(result="unknown", food=None, via=None)

    # Store in cache as generic
    existing = db.get(BarcodeCache, barcode)
    if not existing:
        existing = BarcodeCache(
            barcode=barcode,
            source="generic",
            title=term,
            found=True,
            lookup_attempted_at=utcnow(),
            created_at=utcnow(),
        )
        db.add(existing)
        db.commit()

    # Search mealie_foods
    foods = db.query(MealieFood).all()
    best_score = 0
    best_food = None
    for food in foods:
        score = fuzz.token_sort_ratio(term.lower(), food.name.lower())
        if food.aliases:
            try:
                aliases = json.loads(food.aliases)
                for alias in aliases:
                    alias_score = fuzz.token_sort_ratio(term.lower(), alias.lower())
                    score = max(score, alias_score)
            except (json.JSONDecodeError, TypeError):
                pass
        if score > best_score:
            best_score = score
            best_food = food

    if best_food and best_score >= settings.fuzzy_match_threshold:
        return _add_via_food_id(best_food.id, best_food.name, barcode, db)

    # Fallback: add as note
    success = add_to_shopping_list_by_note(term)
    if success:
        return ScanResponse(result="added_as_note", food=term, via="note")
    else:
        _enqueue_note(barcode, term, db)
        return ScanResponse(result="queued", food=term, via="note")


def _add_via_food_id(food_id: str, food_name: str, barcode: str, db: Session) -> ScanResponse:
    """Try adding via food_id; queue on failure."""
    success = add_to_shopping_list_by_food(food_id)
    if success:
        return ScanResponse(result="added", food=food_name, via="food_id")
    else:
        payload = {
            "shoppingListId": settings.mealie_shopping_list_id,
            "foodId": food_id,
            "quantity": 1,
        }
        enqueue_retry(barcode, payload, db)
        return ScanResponse(result="queued", food=food_name, via="food_id")


def _enqueue_note(barcode: str, note: str, db: Session) -> None:
    """Enqueue a note-based shopping list addition for retry."""
    payload = {
        "shoppingListId": settings.mealie_shopping_list_id,
        "note": note,
    }
    enqueue_retry(barcode, payload, db)
