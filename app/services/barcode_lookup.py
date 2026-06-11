import json
import logging
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BarcodeCache
from app.utils import utcnow

logger = logging.getLogger(__name__)


def lookup_openfoodfacts(barcode: str) -> dict | None:
    """Query OpenFoodFacts. Returns product dict or None."""
    if not settings.off_enabled:
        return None
    url = f"{settings.off_url_base}{barcode}.json"
    try:
        resp = httpx.get(url, timeout=5)
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
        resp = httpx.get(url, params={"apikey": settings.upcdb_api_key}, timeout=5)
        logger.info(f"UPCDatabase {barcode}: HTTP {resp.status_code}")
        if resp.status_code != 200:
            return None
        # UPCDatabase sometimes prepends stray HTML before the JSON
        text = resp.text
        match = re.search(r'\{\s*"', text)
        if not match:
            logger.warning(f"UPCDatabase {barcode}: no JSON object found in response")
            return None
        clean = text[match.start():]
        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            logger.warning(f"UPCDatabase {barcode}: failed to parse extracted JSON")
            return None
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
    except httpx.HTTPError as e:
        logger.error(f"UPCDatabase error for {barcode}: {e}")
        return None


def _get_lookup_functions() -> tuple:
    """Return (primary_fn, secondary_fn) based on LOOKUP_PRIMARY config.

    Each function is the raw lookup callable.  If a source is disabled or
    missing its API key the corresponding slot is ``None``.
    """
    off_fn = lookup_openfoodfacts if settings.off_enabled else None
    upcdb_fn = (
        lookup_upcdatabase
        if settings.upcdb_enabled and settings.upcdb_api_key
        else None
    )

    if settings.lookup_primary == "upcdb":
        primary, secondary = upcdb_fn, off_fn
    else:
        primary, secondary = off_fn, upcdb_fn

    # If the chosen primary is unavailable, swap.
    if primary is None:
        primary, secondary = secondary, None

    return primary, secondary


def _result_has_gaps(result: dict) -> bool:
    """True when any enrichment field is empty."""
    return not all(result.get(f) for f in ("brand", "quantity", "product_type"))


def _merge_gaps(base: dict, supplement: dict) -> bool:
    """Fill empty enrichment fields in *base* from *supplement*.

    Returns True if any field was actually filled.
    """
    changed = False
    for field in ("brand", "quantity", "product_type"):
        if not base.get(field) and supplement.get(field):
            base[field] = supplement[field]
            changed = True
    if changed:
        base["source"] = f"{base['source']}+{supplement['source']}"
    return changed


def perform_lookup(barcode: str, db: Session) -> BarcodeCache:
    """Lookup barcode in external APIs and upsert into barcode_cache.

    Strategy (``LOOKUP_STRATEGY``):
    * ``failover`` — try primary, use secondary only if primary returns
      nothing.  (Default, current behaviour.)
    * ``complement`` — try primary, respond with whatever it gives, then
      (optionally in background) fill gaps from the secondary.
      When ``LOOKUP_ENRICH_IN_BACKGROUND`` is *False* the secondary call
      is made synchronously before returning.

    Returns the cache row.  When complement+background mode is active the
    caller is expected to schedule ``enrich_barcode_background()`` *after*
    sending the HTTP response.
    """
    primary_fn, secondary_fn = _get_lookup_functions()

    result = None
    if primary_fn:
        result = primary_fn(barcode)

    if not result:
        # Primary returned nothing — always try secondary as full fallback
        # regardless of strategy (we need *something*).
        if secondary_fn:
            result = secondary_fn(barcode)
    elif (
        settings.lookup_strategy == "complement"
        and not settings.lookup_enrich_in_background
        and secondary_fn
        and _result_has_gaps(result)
    ):
        # Complement mode, synchronous: fill gaps right now.
        supplement = secondary_fn(barcode)
        if supplement:
            _merge_gaps(result, supplement)

    # --- upsert cache ---
    existing = db.get(BarcodeCache, barcode)
    now = utcnow()

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


def needs_background_enrich(cached: BarcodeCache) -> bool:
    """Return True if a background enrichment call should be scheduled."""
    if settings.lookup_strategy != "complement":
        return False
    if not settings.lookup_enrich_in_background:
        return False  # already done synchronously
    if not cached.found:
        return False
    _, secondary_fn = _get_lookup_functions()
    if secondary_fn is None:
        return False
    return not all([cached.brand, cached.quantity, cached.product_type])


def enrich_barcode_background(barcode: str) -> None:
    """Background task: call secondary API and fill gaps in cache.

    Runs outside the request lifecycle — creates its own DB session.
    """
    from app.database import SessionLocal

    _, secondary_fn = _get_lookup_functions()
    if secondary_fn is None:
        return

    supplement = secondary_fn(barcode)
    if not supplement:
        logger.info("Background enrich %s: secondary returned nothing", barcode)
        return

    db = SessionLocal()
    try:
        cached = db.get(BarcodeCache, barcode)
        if not cached or not cached.found:
            return

        changed = False
        for field in ("brand", "quantity", "product_type"):
            if not getattr(cached, field) and supplement.get(field):
                setattr(cached, field, supplement[field])
                changed = True

        if changed:
            cached.source = f"{cached.source}+{supplement['source']}"
            db.commit()
            logger.info("Background enrich %s: filled gaps → %s", barcode, cached.source)
        else:
            logger.debug("Background enrich %s: no new data from secondary", barcode)
    finally:
        db.close()
