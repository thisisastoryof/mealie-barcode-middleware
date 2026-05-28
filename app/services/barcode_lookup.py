import json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BarcodeCache

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def lookup_openfoodfacts(barcode: str) -> dict | None:
    """Query OpenFoodFacts. Returns product dict or None."""
    if not settings.off_enabled:
        return None
    url = f"{settings.off_url_base}{barcode}.json"
    try:
        resp = httpx.get(url, timeout=10)
        logger.info(f"OpenFoodFacts {barcode}: HTTP {resp.status_code}")
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("status") != 1:
            return None
        product = data.get("product", {})
        name = product.get("product_name") or ""
        if not name.strip():
            return None
        return {
            "title": name.strip(),
            "brand": (product.get("brands") or "").split(",")[0].strip(),
            "product_type": (product.get("product_type") or "").split(",")[0].strip() or None,
            "quantity": (product.get("quantity") or "").strip() or None,
            "source": "openfoodfacts",
        }
    except httpx.HTTPError as e:
        logger.error(f"OpenFoodFacts error for {barcode}: {e}")
        return None


def lookup_upcdatabase(barcode: str) -> dict | None:
    """Query UPCDatabase. Returns product dict or None."""
    if not settings.upcdb_enabled:
        return None
    if not settings.upcdb_api_key:
        return None
    url = f"{settings.upcdb_url_base}{barcode}"
    try:
        resp = httpx.get(url, params={"apikey": settings.upcdb_api_key}, timeout=10)
        logger.info(f"UPCDatabase {barcode}: HTTP {resp.status_code}")
        if resp.status_code != 200:
            return None
        # UPCDatabase sometimes prepends stray HTML before the JSON
        text = resp.text
        json_start = text.find("{")
        if json_start == -1:
            return None
        clean = text[json_start:]
        data = json.loads(clean)
        if not data.get("success"):
            return None
        title = data.get("title") or data.get("alias") or data.get("description") or ""
        if not title.strip():
            return None
        metadata = data.get("metadata") or {}
        return {
            "title": title.strip(),
            "brand": (data.get("brand") or "").split(",")[0].strip(),
            "product_type": (data.get("category") or "").split(",")[0].strip().lower() or None,
            "quantity": (metadata.get("quantity") or "").split(",")[0].strip() or None,
            "source": "upcdatabase",
        }
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        logger.error(f"UPCDatabase error for {barcode}: {e}")
        return None


def perform_lookup(barcode: str, db: Session) -> BarcodeCache:
    """Lookup barcode in external APIs and upsert into barcode_cache. Returns the cache row."""
    # Try OpenFoodFacts first
    result = lookup_openfoodfacts(barcode)
    if not result:
        result = lookup_upcdatabase(barcode)

    existing = db.get(BarcodeCache, barcode)
    now = _utcnow()

    if result:
        if existing:
            existing.source = result["source"]
            existing.title = result["title"]
            existing.brand = result["brand"]
            existing.quantity = result["quantity"]
            existing.product_type = result["product_type"]
            existing.found = True
            existing.lookup_attempted_at = now
        else:
            existing = BarcodeCache(
                barcode=barcode,
                source=result["source"],
                title=result["title"],
                brand=result["brand"],
                quantity=result["quantity"],
                product_type=result["product_type"],
                found=True,
                lookup_attempted_at=now,
                created_at=now,
            )
            db.add(existing)
    else:
        if existing:
            existing.source = "not_found"
            existing.found = False
            existing.lookup_attempted_at = now
        else:
            existing = BarcodeCache(
                barcode=barcode,
                source="not_found",
                found=False,
                lookup_attempted_at=now,
                created_at=now,
            )
            db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing
