import logging

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import generate_token, hash_token
from app.config import settings, EDITABLE_SETTINGS, READONLY_SETTINGS
from app.database import get_db
from app.models import ApiToken
from app.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()

# Ordered groups for the settings page
_GROUP_ORDER = [
    "Mealie Connection",
    "Barcode Lookup Sources",
    "Matching & Sync",
    "System",
]


def _build_config_groups():
    """Build the config groups with editable/readonly metadata for the template."""
    groups: dict[str, list] = {g: [] for g in _GROUP_ORDER}

    # Readonly settings first (within each group)
    for key, meta in READONLY_SETTINGS.items():
        group = meta["group"]
        if meta.get("secret"):
            val = "***" if getattr(settings, key) else "(not set)"
        else:
            val = getattr(settings, key)
            if val is None or val == "":
                val = "(not set)"
            else:
                val = str(val)
        groups.setdefault(group, []).append({
            "key": meta["label"],
            "field": key,
            "value": val,
            "description": meta["description"],
            "editable": False,
        })

    # Editable settings
    for key, meta in EDITABLE_SETTINGS.items():
        group = meta["group"]
        val = settings.get_display_value(key)
        overridden = settings.is_overridden(key)
        env_default = str(settings.get_env_default(key))
        groups.setdefault(group, []).append({
            "key": meta["label"],
            "field": key,
            "value": val,
            "description": meta["description"],
            "editable": True,
            "overridden": overridden,
            "env_default": env_default,
            "type": meta["type"],
            "choices": meta.get("choices"),
            "min": meta.get("min"),
            "max": meta.get("max"),
        })

    return [(g, groups[g]) for g in _GROUP_ORDER if groups.get(g)]


# Tab definitions: id → (label, icon, group heading)
_TABS = [
    ("mealie",   "Mealie Connection",  "ti-plug"),
    ("lookup",   "Barcode Lookup",     "ti-barcode"),
    ("matching", "Matching & Sync",    "ti-arrows-sort"),
    ("system",   "System",             "ti-settings"),
    ("tokens",   "API Tokens",         "ti-key"),
]

# Which config groups map to which tab
_TAB_GROUPS = {
    "mealie":   ["Mealie Connection"],
    "lookup":   ["Barcode Lookup Sources"],
    "matching": ["Matching & Sync"],
    "system":   ["System"],
}


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, tab: str = Query("mealie"), db: Session = Depends(get_db)):
    all_groups = _build_config_groups()
    # Filter groups for the active tab
    active_groups = _TAB_GROUPS.get(tab, [])
    tab_groups = [(name, items) for name, items in all_groups if name in active_groups]
    tokens = db.query(ApiToken).order_by(ApiToken.created_at.desc()).all() if tab == "tokens" else []
    saved = request.query_params.get("saved")

    return templates.TemplateResponse(request, "settings.html", {
        "tabs": _TABS,
        "current_tab": tab,
        "config_groups": tab_groups,
        "tokens": tokens,
        "new_token": None,
        "saved": saved,
    })


@router.post("/settings/configuration", response_class=HTMLResponse)
async def save_settings(request: Request, db: Session = Depends(get_db)):
    """Save editable settings from the form."""
    form_data = await request.form()

    changed = []
    for key, meta in EDITABLE_SETTINGS.items():
        form_key = f"setting_{key}"
        if meta["type"] == "bool":
            # Checkboxes: present = True, absent = False
            new_val = "true" if form_key in form_data else "false"
        else:
            new_val = form_data.get(form_key)
            if new_val is None:
                continue

        new_val = new_val.strip()
        current_val = settings.get_display_value(key)
        if new_val != current_val:
            try:
                settings.save_override(key, new_val, db)
                changed.append(key)
            except ValueError as e:
                logger.warning("Invalid setting %s=%s: %s", key, new_val, e)

    if changed:
        logger.info("Settings updated via UI: %s", ", ".join(changed))

    # Redirect back to the originating tab
    tab = form_data.get("_tab", "mealie")
    return RedirectResponse(f"/settings?tab={tab}&saved=1", status_code=303)


@router.post("/settings/configuration/{field}/reset")
def reset_setting(field: str, db: Session = Depends(get_db)):
    """Reset a single setting to its env/default value."""
    if field not in EDITABLE_SETTINGS:
        return RedirectResponse("/settings?tab=mealie", status_code=303)

    # Determine which tab this field belongs to
    group = EDITABLE_SETTINGS[field].get("group", "")
    tab = "mealie"
    for tab_id, groups in _TAB_GROUPS.items():
        if group in groups:
            tab = tab_id
            break

    settings.reset_override(field, db)
    logger.info("Setting '%s' reset to env default via UI", field)
    return RedirectResponse(f"/settings?tab={tab}&saved=1", status_code=303)


@router.post("/settings/tokens/create", response_class=HTMLResponse)
def create_token(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    raw = generate_token()
    hashed = hash_token(raw)
    token = ApiToken(name=name, token_hash=hashed, token_prefix=raw[:8])
    db.add(token)
    db.commit()
    db.refresh(token)

    tokens = db.query(ApiToken).order_by(ApiToken.created_at.desc()).all()
    return templates.TemplateResponse(request, "settings.html", {
        "tabs": _TABS,
        "config_groups": [],
        "tokens": tokens,
        "current_tab": "tokens",
        "new_token": raw,
        "new_token_name": name,
        "saved": None,
    })


@router.post("/settings/tokens/{token_id}/delete")
def delete_token(token_id: str, db: Session = Depends(get_db)):
    token = db.get(ApiToken, token_id)
    if token:
        db.delete(token)
        db.commit()
    return RedirectResponse("/settings?tab=tokens", status_code=303)
