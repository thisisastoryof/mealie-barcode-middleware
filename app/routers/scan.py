import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_token
from app.config import settings
from app.database import get_db
from app.events import scan_events
from app.models import BarcodeCache, BarcodeMapping, Item, Notification
from app.services.barcode_lookup import perform_lookup
from app.services.fuzzy import try_auto_map
from app.services.mealie import (
    add_to_shopping_list_by_item,
    add_to_shopping_list_by_note,
    enqueue_retry,
)
from app.utils import utcnow, sanitize_for_display

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_action_url(barcode: str) -> str:
    """Build a deep link URL for HA notifications."""
    base = settings.middleware_base_url.rstrip("/")
    if base:
        return f"{base}/barcodes/{barcode}"
    return f"/barcodes/{barcode}"


class ScanRequest(BaseModel):
    barcode: str = Field(..., max_length=256)


class ScanResponse(BaseModel):
    result: str  # added | added_as_note | queued | unknown
    item: str | None = None
    via: str | None = None  # item_id | note
    needs_action: bool = False
    action_url: str | None = None
    brand: str | None = None
    quantity: str | None = None
    item_source: str | None = None  # mealie | manual | None


@router.post("/scan", response_model=ScanResponse)
def scan_barcode(
    body: ScanRequest,
    _token=Depends(require_token),
    db: Session = Depends(get_db),
):
    barcode = body.barcode.strip()
    if not barcode:
        return ScanResponse(result="unknown", item=None, via=None)

    try:
        return _process_scan(barcode, db)
    except Exception:
        logger.exception("Unhandled error processing scan for barcode %s", barcode)
        db.rollback()
        return ScanResponse(result="error", item=barcode, via=None)


def _process_scan(barcode: str, db: Session) -> ScanResponse:

    # --- GENERIC QR code handling ---
    if barcode.upper().startswith("GENERIC:"):
        term = barcode[len("GENERIC:"):].strip()
        resp = _handle_generic(term, barcode, db)
        _emit_scan_event(barcode, resp)
        return resp

    # --- Standard barcode flow ---
    # Step 1: Check existing mapping
    mapping = db.get(BarcodeMapping, barcode)
    if mapping:
        item = db.get(Item, mapping.item_id)
        item_name = item.name if item else barcode
        cached = db.get(BarcodeCache, barcode)
        resp = _add_via_item(item, item_name, barcode, db, cached=cached)
        _emit_scan_event(barcode, resp)
        _save_activity(barcode, "Added to list", item_name, resp.result, db)
        return resp

    # Step 2: Check cache / perform lookup
    cached = db.get(BarcodeCache, barcode)
    needs_lookup = False

    if cached is None:
        needs_lookup = True
    elif not cached.found:
        # Check TTL
        if cached.lookup_attempted_at:
            attempted = cached.lookup_attempted_at
            if attempted.tzinfo is None:
                attempted = attempted.replace(tzinfo=timezone.utc)
            ttl_expiry = attempted + timedelta(days=settings.lookup_ttl_days)
            if utcnow() > ttl_expiry:
                needs_lookup = True

    if needs_lookup:
        cached = perform_lookup(barcode, db)

    if not cached.found:
        # Not found anywhere — add as note with barcode string
        note = barcode
        success = add_to_shopping_list_by_note(note)
        if success:
            resp = ScanResponse(result="unknown", item=barcode, via="note")
        else:
            _enqueue_note(barcode, note, db)
            resp = ScanResponse(result="unknown", item=barcode, via="note")
        resp.needs_action = True
        resp.action_url = _build_action_url(barcode)
        _emit_scan_event(barcode, resp)
        _save_notification(barcode, "Unknown barcode", f"Not found in any product database", "unknown", db)
        return resp

    # Step 3: Attempt fuzzy auto-mapping
    item_id = try_auto_map(barcode, cached.title or barcode, cached.brand, db)
    if item_id:
        item = db.get(Item, item_id)
        item_name = item.name if item else cached.title or barcode
        resp = _add_via_item(item, item_name, barcode, db, cached=cached)
        resp.needs_action = True
        resp.action_url = _build_action_url(barcode)
        _emit_scan_event(barcode, resp)
        _save_activity(barcode, "Added to list", item_name, resp.result, db)
        _save_notification(barcode, "Auto-mapped — confirm?", f"{cached.title or barcode} → {item_name}", "auto_mapped", db)
        return resp

    # No mapping — add as note with product title
    note = cached.title or barcode
    success = add_to_shopping_list_by_note(note)
    if success:
        resp = ScanResponse(
            result="added_as_note", item=note, via="note",
            brand=cached.brand, quantity=cached.quantity,
            needs_action=True, action_url=_build_action_url(barcode),
        )
        _save_activity(barcode, "Added to list", note + " (via note)", "added_as_note", db)
        _save_notification(barcode, "Mapping needed", f"{note} — assign to a Mealie item", "needs_mapping", db)
    else:
        _enqueue_note(barcode, note, db)
        resp = ScanResponse(
            result="queued", item=note, via="note",
            brand=cached.brand, quantity=cached.quantity,
            needs_action=True, action_url=_build_action_url(barcode),
        )
        _save_activity(barcode, "Queued", note, "queued", db)
    _emit_scan_event(barcode, resp)
    return resp


def _emit_scan_event(barcode: str, resp: ScanResponse):
    """Publish a scan event to all SSE listeners (live alerts only)."""
    scan_events.publish_threadsafe("scan", {
        "barcode": barcode,
        "result": resp.result,
        "item": resp.item,
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


def _save_activity(barcode: str, title: str, message: str, result: str, db: Session):
    """Log a successful scan event (pre-read, doesn't trigger the bell)."""
    db.add(Notification(
        barcode=barcode,
        title=title,
        message=message,
        result=result,
        is_read=True,
    ))
    db.commit()


def _handle_generic(term: str, barcode: str, db: Session) -> ScanResponse:
    """Handle GENERIC: prefixed scans — fuzzy search mealie items."""
    from rapidfuzz import fuzz

    if not term:
        return ScanResponse(result="unknown", item=None, via=None)

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

    # Search items
    all_items = db.query(Item).all()
    best_score = 0
    best_item = None
    for item in all_items:
        score = fuzz.token_sort_ratio(term.lower(), item.name.lower())
        if item.aliases:
            try:
                aliases = json.loads(item.aliases)
                for alias in aliases:
                    alias_score = fuzz.token_sort_ratio(term.lower(), alias.lower())
                    score = max(score, alias_score)
            except (json.JSONDecodeError, TypeError):
                pass
        if score > best_score:
            best_score = score
            best_item = item

    if best_item and best_score >= settings.fuzzy_match_threshold:
        return _add_via_item(best_item, best_item.name, barcode, db)

    # Fallback: add as note
    success = add_to_shopping_list_by_note(term)
    if success:
        return ScanResponse(result="added_as_note", item=term, via="note")
    else:
        _enqueue_note(barcode, term, db)
        return ScanResponse(result="queued", item=term, via="note")


def _add_via_item(
    item: Item | None, item_name: str, barcode: str, db: Session,
    cached: BarcodeCache | None = None,
) -> ScanResponse:
    """Add to shopping list based on item source; queue on failure."""
    brand = cached.brand if cached else None
    quantity = cached.quantity if cached else None
    item_source = item.source if item else None

    if item and item.source == "mealie":
        success = add_to_shopping_list_by_item(item.id)
        if success:
            return ScanResponse(
                result="added", item=item_name, via="item_id",
                brand=brand, quantity=quantity, item_source=item_source,
            )
        else:
            payload = {
                "shoppingListId": settings.mealie_shopping_list_id,
                "foodId": item.id,
                "quantity": 1,
            }
            enqueue_retry(barcode, payload, db)
            return ScanResponse(
                result="queued", item=item_name, via="item_id",
                brand=brand, quantity=quantity, item_source=item_source,
            )
    else:
        note = item.name if item else item_name
        success = add_to_shopping_list_by_note(note)
        if success:
            return ScanResponse(
                result="added", item=note, via="note",
                brand=brand, quantity=quantity, item_source=item_source,
            )
        else:
            _enqueue_note(barcode, note, db)
            return ScanResponse(
                result="queued", item=note, via="note",
                brand=brand, quantity=quantity, item_source=item_source,
            )


def _enqueue_note(barcode: str, note: str, db: Session) -> None:
    """Enqueue a note-based shopping list addition for retry."""
    payload = {
        "shoppingListId": settings.mealie_shopping_list_id,
        "note": note,
    }
    enqueue_retry(barcode, payload, db)
