import json
import logging
import re

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BarcodeFoodMapping, MealieFood

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


def fuzzy_match(
    title: str,
    brand: str | None,
    db: Session,
    threshold: int | None = None,
) -> list[dict]:
    """
    Score normalised title against all mealie_foods.
    Returns list of candidates sorted by score descending.
    Each entry: {"food_id": str, "food_name": str, "score": int}
    """
    if threshold is None:
        threshold = 0  # Return all for ranking; caller filters by threshold

    normalised = normalise_title(title, brand)
    if not normalised:
        return []

    foods = db.query(MealieFood).all()
    candidates = []

    for food in foods:
        # Score against food name
        score = fuzz.token_sort_ratio(normalised.lower(), food.name.lower())
        # Also score against aliases
        aliases = []
        if food.aliases:
            try:
                aliases = json.loads(food.aliases)
            except (json.JSONDecodeError, TypeError):
                pass
        for alias in aliases:
            alias_score = fuzz.token_sort_ratio(normalised.lower(), alias.lower())
            score = max(score, alias_score)

        candidates.append({
            "food_id": food.id,
            "food_name": food.name,
            "score": int(score),
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def try_auto_map(barcode: str, title: str, brand: str | None, db: Session) -> str | None:
    """
    Attempt fuzzy auto-mapping. If top score >= threshold, insert mapping and return food_id.
    Returns None if no match above threshold.
    """
    candidates = fuzzy_match(title, brand, db)
    if not candidates:
        return None

    top = candidates[0]
    if top["score"] >= settings.fuzzy_match_threshold:
        # Insert or update mapping
        existing = db.get(BarcodeFoodMapping, barcode)
        if existing:
            existing.mealie_food_id = top["food_id"]
            existing.mapped_by = "auto"
        else:
            db.add(BarcodeFoodMapping(
                barcode=barcode,
                mealie_food_id=top["food_id"],
                mapped_by="auto",
            ))
        db.commit()
        logger.info(f"Auto-mapped {barcode} → {top['food_name']} (score={top['score']})")
        return top["food_id"]

    return None
