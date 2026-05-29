import json
import logging
import re

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BarcodeMapping, Item

logger = logging.getLogger(__name__)

# Common quantity/size patterns to strip from product titles
_QUANTITY_PATTERN = re.compile(
    r"\b\d+\s*(x\s*\d+\s*)?(g|kg|ml|l|cl|dl|oz|lb|lbs|fl\.?\s*oz|pack|pcs|ct|count)\b",
    re.IGNORECASE,
)
_EXTRA_SPACES = re.compile(r"\s{2,}")


def normalise_title(title: str, brand: str | None = None) -> str:
    """Strip brand and quantity/size info from a product title for matching."""
    result = title
    # Remove brand name if present as substring
    if brand:
        result = re.sub(re.escape(brand), "", result, flags=re.IGNORECASE)
    # Remove quantity patterns
    result = _QUANTITY_PATTERN.sub("", result)
    # Remove common separators and extra spaces
    result = result.replace("-", " ").replace("_", " ")
    result = _EXTRA_SPACES.sub(" ", result).strip()
    return result


def _score_pair(product: str, food_term: str) -> int:
    """
    Score a normalised product title against a single food name/alias.
    Uses max of token_sort_ratio, token_set_ratio, and partial_ratio
    for best coverage across languages and partial matches.
    """
    p = product.lower()
    f = food_term.lower()
    return max(
        fuzz.token_sort_ratio(p, f),
        fuzz.token_set_ratio(p, f),
        fuzz.partial_ratio(p, f),
    )


def fuzzy_match(
    title: str,
    brand: str | None,
    db: Session,
    threshold: int | None = None,
) -> list[dict]:
    """
    Score normalised title against all items.
    Returns list of candidates sorted by score descending.
    Each entry: {"item_id": str, "item_name": str, "score": int, "source": str}
    """
    if threshold is None:
        threshold = 0  # Return all for ranking; caller filters by threshold

    normalised = normalise_title(title, brand)
    if not normalised:
        return []

    items = db.query(Item).all()
    candidates = []

    for item in items:
        # Score against item name
        score = _score_pair(normalised, item.name)
        # Also score against aliases
        aliases = []
        if item.aliases:
            try:
                aliases = json.loads(item.aliases)
            except (json.JSONDecodeError, TypeError):
                pass
        for alias in aliases:
            alias_score = _score_pair(normalised, alias)
            score = max(score, alias_score)

        candidates.append({
            "item_id": item.id,
            "item_name": item.name,
            "source": item.source,
            "score": int(score),
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def try_auto_map(barcode: str, title: str, brand: str | None, db: Session) -> str | None:
    """
    Attempt fuzzy auto-mapping.
    Only maps if:
      1. Top score >= threshold
      2. Gap between #1 and #2 >= ambiguity_gap (avoids false matches when
         multiple foods match equally, e.g. "Tuna" and "Water" both appearing
         in "Chunk Light Tuna in Water")
    Returns food_id on success, None otherwise.
    """
    candidates = fuzzy_match(title, brand, db)
    if not candidates:
        return None

    top = candidates[0]
    if top["score"] < settings.fuzzy_match_threshold:
        return None

    # Ambiguity check: ensure clear winner
    if len(candidates) >= 2:
        second = candidates[1]
        gap = top["score"] - second["score"]
        if gap < settings.fuzzy_ambiguity_gap:
            logger.info(
                f"Ambiguous match for {barcode}: "
                f"{top['item_name']}({top['score']}) vs "
                f"{second['item_name']}({second['score']}), gap={gap} < {settings.fuzzy_ambiguity_gap}"
            )
            return None

    # Clear winner — insert or update mapping
    existing = db.get(BarcodeMapping, barcode)
    if existing:
        existing.item_id = top["item_id"]
        existing.mapped_by = "auto"
    else:
        db.add(BarcodeMapping(
            barcode=barcode,
            item_id=top["item_id"],
            mapped_by="auto",
        ))
    db.commit()
    logger.info(f"Auto-mapped {barcode} → {top['item_name']} (score={top['score']})")
    return top["item_id"]
