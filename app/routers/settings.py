import logging

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import generate_token, hash_token
from app.config import settings
from app.database import get_db
from app.models import ApiToken

logger = logging.getLogger(__name__)
router = APIRouter()


def _templates():
    from app.main import templates
    return templates


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, tab: str = Query("configuration"), db: Session = Depends(get_db)):
    config_groups = [
        ("Mealie Connection", [
            ("MEALIE_URL", settings.mealie_url, "Base URL of your Mealie instance"),
            ("MEALIE_SHOPPING_LIST_ID", settings.mealie_shopping_list_id, "Shopping list where scanned items are added"),
        ]),
        ("Barcode Lookup Sources", [
            ("OFF_ENABLED", str(settings.off_enabled), "Use Open Food Facts for barcode lookups"),
            ("OFF_URL_BASE", settings.off_url_base, "Open Food Facts API endpoint"),
            ("UPCDB_ENABLED", str(settings.upcdb_enabled), "Use UPC Database as fallback lookup source"),
            ("UPCDB_URL_BASE", settings.upcdb_url_base, "UPC Database API endpoint"),
            ("UPCDB_API_KEY", "***" if settings.upcdb_api_key else "(not set)", "API key for UPC Database"),
        ]),
        ("Matching & Sync", [
            ("FUZZY_MATCH_THRESHOLD", str(settings.fuzzy_match_threshold), "Minimum score (0–100) to accept a fuzzy food match"),
            ("FUZZY_AMBIGUITY_GAP", str(settings.fuzzy_ambiguity_gap), "Min. score gap between top two matches to avoid ambiguity"),
            ("FOOD_SYNC_INTERVAL_HOURS", str(settings.food_sync_interval_hours), "How often the Mealie food list is re-synced"),
            ("LOOKUP_TTL_DAYS", str(settings.lookup_ttl_days), "Days before a cached barcode lookup expires"),
            ("MAX_RETRY_ATTEMPTS", str(settings.max_retry_attempts), "Max retries before a queued item is marked as failed"),
        ]),
        ("System", [
            ("TIMEZONE", settings.timezone, "Timezone used for timestamps and scheduling"),
            ("DB_PATH", settings.db_path, "Path to the SQLite database file"),
            ("PORT", str(settings.port), "HTTP port the middleware listens on"),
            ("LOG_LEVEL", settings.log_level, "Application log verbosity"),
        ]),
    ]

    tokens = db.query(ApiToken).order_by(ApiToken.created_at.desc()).all() if tab == "tokens" else []

    return _templates().TemplateResponse(request, "settings.html", {
        "config_groups": config_groups,
        "tokens": tokens,
        "current_tab": tab,
        "new_token": None,
    })


@router.get("/settings/tokens")
def tokens_redirect():
    return RedirectResponse("/settings?tab=tokens", status_code=302)


@router.post("/settings/tokens/create", response_class=HTMLResponse)
def create_token(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    raw = generate_token()
    hashed = hash_token(raw)
    token = ApiToken(name=name, token_hash=hashed)
    db.add(token)
    db.commit()
    db.refresh(token)

    tokens = db.query(ApiToken).order_by(ApiToken.created_at.desc()).all()
    return _templates().TemplateResponse(request, "settings.html", {
        "config_groups": [],
        "tokens": tokens,
        "current_tab": "tokens",
        "new_token": raw,
        "new_token_name": name,
    })


@router.post("/settings/tokens/{token_id}/delete")
def delete_token(token_id: str, db: Session = Depends(get_db)):
    token = db.get(ApiToken, token_id)
    if token:
        db.delete(token)
        db.commit()
    return RedirectResponse("/settings?tab=tokens", status_code=303)
    return RedirectResponse("/settings/tokens", status_code=303)
