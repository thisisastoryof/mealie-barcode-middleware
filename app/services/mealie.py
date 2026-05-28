import json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MealieFood, RetryQueue

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


def sync_foods(db: Session) -> int:
    """Fetch all foods from Mealie and upsert into mealie_foods table. Returns count."""
    url = f"{settings.mealie_url}/api/foods"
    try:
        resp = httpx.get(url, headers=_headers(), params={"perPage": -1}, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"Failed to sync foods from Mealie: {e}")
        raise

    data = resp.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    now = _utcnow()
    count = 0

    for food in items:
        food_id = food.get("id")
        if not food_id:
            continue
        name = food.get("name") or food.get("label") or ""
        aliases_raw = food.get("aliases") or []
        aliases_list = [a.get("name", a) if isinstance(a, dict) else a for a in aliases_raw]
        aliases_json = json.dumps(aliases_list)

        existing = db.get(MealieFood, food_id)
        if existing:
            existing.name = name
            existing.aliases = aliases_json
            existing.synced_at = now
        else:
            db.add(MealieFood(id=food_id, name=name, aliases=aliases_json, synced_at=now))
        count += 1

    db.commit()
    logger.info(f"Synced {count} foods from Mealie")
    return count


def add_to_shopping_list_by_food(food_id: str) -> bool:
    """Add item to Mealie shopping list via food ID."""
    payload = {
        "shoppingListId": settings.mealie_shopping_list_id,
        "foodId": food_id,
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
        resp = httpx.post(url, headers=_headers(), json=payload, timeout=10)
        if resp.status_code in (200, 201):
            return True
        logger.warning(f"Mealie shopping POST returned {resp.status_code}: {resp.text}")
        return False
    except httpx.HTTPError as e:
        logger.error(f"Mealie shopping POST failed: {e}")
        return False


def enqueue_retry(barcode: str, payload: dict, db: Session) -> None:
    """Add a failed Mealie request to the retry queue."""
    db.add(RetryQueue(
        barcode=barcode,
        payload=json.dumps(payload),
        attempts=0,
        next_retry_at=_utcnow(),
        created_at=_utcnow(),
    ))
    db.commit()
