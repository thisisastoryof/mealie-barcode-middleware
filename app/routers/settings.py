import logging

from fastapi import APIRouter, Depends, Form, Request
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
def settings_page(request: Request):
    config_display = {
        "MEALIE_URL": settings.mealie_url,
        "MEALIE_SHOPPING_LIST_ID": settings.mealie_shopping_list_id,
        "OFF_URL_BASE": settings.off_url_base,
        "UPCDB_URL_BASE": settings.upcdb_url_base,
        "UPCDB_API_KEY": "***" if settings.upcdb_api_key else "(not set)",
        "FOOD_SYNC_INTERVAL_HOURS": str(settings.food_sync_interval_hours),
        "FUZZY_MATCH_THRESHOLD": str(settings.fuzzy_match_threshold),
        "LOOKUP_TTL_DAYS": str(settings.lookup_ttl_days),
        "DB_PATH": settings.db_path,
        "PORT": str(settings.port),
        "LOG_LEVEL": settings.log_level,
    }
    return _templates().TemplateResponse("settings.html", {
        "request": request,
        "config": config_display,
    })


@router.get("/settings/tokens", response_class=HTMLResponse)
def tokens_page(request: Request, db: Session = Depends(get_db)):
    tokens = db.query(ApiToken).order_by(ApiToken.created_at.desc()).all()
    return _templates().TemplateResponse("tokens.html", {
        "request": request,
        "tokens": tokens,
        "new_token": None,
    })


@router.post("/settings/tokens/create", response_class=HTMLResponse)
def create_token(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    raw = generate_token()
    hashed = hash_token(raw)
    token = ApiToken(name=name, token_hash=hashed)
    db.add(token)
    db.commit()
    db.refresh(token)

    tokens = db.query(ApiToken).order_by(ApiToken.created_at.desc()).all()
    return _templates().TemplateResponse("tokens.html", {
        "request": request,
        "tokens": tokens,
        "new_token": raw,
        "new_token_name": name,
    })


@router.post("/settings/tokens/{token_id}/delete")
def delete_token(token_id: str, db: Session = Depends(get_db)):
    token = db.get(ApiToken, token_id)
    if token:
        db.delete(token)
        db.commit()
    return RedirectResponse("/settings/tokens", status_code=303)
