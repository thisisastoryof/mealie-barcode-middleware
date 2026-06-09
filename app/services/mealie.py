import json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BarcodeMapping, Item, Notification, RetryQueue
from app.utils import utcnow

logger = logging.getLogger(__name__)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.mealie_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def check_connectivity() -> bool:
    """Check if Mealie is reachable."""
    try:
        resp = httpx.get(
            f"{settings.mealie_url}/api/app/about",
            headers=_headers(),
            timeout=5,
        )
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


def sync_items(db: Session) -> int:
    """Fetch all items from Mealie, upsert into items table, detect stale. Returns count."""
    url = f"{settings.mealie_url}/api/foods"
    try:
        resp = httpx.get(url, headers=_headers(), params={"perPage": -1}, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"Failed to sync items from Mealie: {e}")
        raise

    data = resp.json()
    if isinstance(data, dict):
        items = data.get("items")
        if items is None:
            logger.error(f"Unexpected Mealie response structure: {list(data.keys())}")
            raise ValueError("Mealie API returned unexpected response (no 'items' key)")
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(f"Mealie API returned unexpected type: {type(data).__name__}")
    sync_started = utcnow()
    count = 0

    for food in items:
        item_id = food.get("id")
        if not item_id:
            continue
        name = food.get("name") or food.get("label") or ""
        aliases_raw = food.get("aliases") or []
        aliases_list = [a.get("name", a) if isinstance(a, dict) else a for a in aliases_raw]
        aliases_json = json.dumps(aliases_list)

        existing = db.get(Item, item_id)
        if existing:
            existing.name = name
            existing.aliases = aliases_json
            existing.synced_at = sync_started
        else:
            db.add(Item(id=item_id, name=name, source="mealie", aliases=aliases_json, synced_at=sync_started))
        count += 1

    db.flush()

    # Detect stale items (deleted in Mealie since last sync)
    stale_items = (
        db.query(Item)
        .filter(Item.source == "mealie", Item.synced_at < sync_started)
        .all()
    )
    for stale in stale_items:
        # Find broken mappings
        broken = db.query(BarcodeMapping).filter(BarcodeMapping.item_id == stale.id).all()
        for m in broken:
            db.add(Notification(
                barcode=m.barcode,
                title="Mapping broken",
                message=f"{stale.name} was deleted in Mealie — remap needed",
                result="broken",
            ))
            db.delete(m)
        db.delete(stale)
        if broken:
            logger.warning(f"Stale item '{stale.name}' removed, {len(broken)} mapping(s) broken")

    db.commit()
    logger.info(f"Synced {count} items from Mealie")
    return count


def add_to_shopping_list_by_item(item_id: str) -> bool:
    """Add item to Mealie shopping list via food ID."""
    payload = {
        "shoppingListId": settings.mealie_shopping_list_id,
        "foodId": item_id,
        "quantity": 1,
    }
    return _post_shopping_item(payload)


def add_to_shopping_list_by_note(note: str) -> bool:
    """Add item to Mealie shopping list via plain note."""
    payload = {
        "shoppingListId": settings.mealie_shopping_list_id,
        "note": note,
    }
    return _post_shopping_item(payload)


def _post_shopping_item(payload: dict) -> bool:
    """POST to Mealie shopping items endpoint. Returns True on success."""
    url = f"{settings.mealie_url}/api/households/shopping/items"
    try:
        resp = httpx.post(url, headers=_headers(), json=payload, timeout=3)
        if resp.status_code in (200, 201):
            return True
        logger.warning(f"Mealie shopping POST returned {resp.status_code}: {resp.text}")
        return False
    except httpx.HTTPError as e:
        logger.error(f"Mealie shopping POST failed: {e}")
        return False


def enqueue_retry(barcode: str, payload: dict, db: Session) -> None:
    """Add a failed Mealie request to the retry queue (skip if already pending)."""
    existing = db.query(RetryQueue).filter(RetryQueue.barcode == barcode).first()
    if existing:
        logger.info(f"Retry entry already pending for barcode={barcode}, skipping duplicate")
        return
    db.add(RetryQueue(
        barcode=barcode,
        payload=json.dumps(payload),
        attempts=0,
        next_retry_at=utcnow(),
        created_at=utcnow(),
    ))
    db.commit()
