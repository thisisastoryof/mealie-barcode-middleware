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

# Tab-level descriptions shown below the heading
_TAB_DESCRIPTIONS = {
    "mealie": "Connection details for your Mealie instance. Set via environment variables.",
    "lookup": "Configure which product databases to query and how they interact.",
    "matching": "Control how scanned products are matched and synced with Mealie.",
    "system": "General system configuration.",
    "tokens": "Bearer tokens for authenticating scanner devices.",
}

# Section-level descriptions shown below section headings
_SECTION_DESCRIPTIONS = {
    "Data Sources": "Enable the product databases used for barcode lookups.",
    "Strategy": "Control how multiple data sources work together.",
    "Fuzzy Matching": "How product names are compared against your Mealie food catalog.",
    "Scheduling & Retry": "How often data is refreshed and how failures are handled.",
    "Infrastructure": "Configured via environment variables.",
}


def _build_config_groups():
    """Build config groups with section sub-grouping for the template.

    Returns [(group_name, [(section_name, [items])])].
    Within each section, editable items appear before readonly items.
    """
    group_items: dict[str, list] = {g: [] for g in _GROUP_ORDER}

    # Process editable first so they appear before readonly within sections
    for key, meta in EDITABLE_SETTINGS.items():
        group = meta["group"]
        val = settings.get_display_value(key)
        overridden = settings.is_overridden(key)
        env_default = str(settings.get_env_default(key))
        group_items.setdefault(group, []).append({
            "key": meta["label"],
            "field": key,
            "value": val,
            "description": meta["description"],
            "hint": meta.get("hint"),
            "editable": True,
            "overridden": overridden,
            "env_default": env_default,
            "type": meta["type"],
            "choices": meta.get("choices"),
            "min": meta.get("min"),
            "max": meta.get("max"),
            "section": meta.get("section", ""),
        })

    # Then readonly
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
        group_items.setdefault(group, []).append({
            "key": meta["label"],
            "field": key,
            "value": val,
            "description": meta["description"],
            "hint": meta.get("hint"),
            "editable": False,
            "section": meta.get("section", ""),
        })

    # Sub-group items by section within each group, preserving insertion order
    result = []
    for g in _GROUP_ORDER:
        items = group_items.get(g)
        if not items:
            continue
        section_map: dict[str, list] = {}
        section_order: list[str] = []
        for item in items:
            sec = item["section"]
            if sec not in section_map:
                section_map[sec] = []
                section_order.append(sec)
            section_map[sec].append(item)
        sections = [(s, section_map[s]) for s in section_order]
        result.append((g, sections))

    return result


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
    tab_groups = [(name, sections) for name, sections in all_groups if name in active_groups]
    has_editable = any(
        item["editable"]
        for _, sections in tab_groups
        for _, items in sections
        for item in items
    )
    tokens = db.query(ApiToken).order_by(ApiToken.created_at.desc()).all() if tab == "tokens" else []

    # Resolve the current tab label for the content heading
    tab_label = next((label for tid, label, _ in _TABS if tid == tab), tab.title())

    return templates.TemplateResponse(request, "settings.html", {
        "tabs": _TABS,
        "current_tab": tab,
        "current_tab_label": tab_label,
        "tab_description": _TAB_DESCRIPTIONS.get(tab, ""),
        "section_descriptions": _SECTION_DESCRIPTIONS,
        "config_groups": tab_groups,
        "has_editable": has_editable,
        "tokens": tokens,
        "new_token": None,
    })


@router.post("/settings/configuration", response_class=HTMLResponse)
async def save_settings(request: Request, db: Session = Depends(get_db)):
    """Save editable settings from the form."""
    form_data = await request.form()
    tab = form_data.get("_tab", "mealie")

    # Only process settings that belong to the current tab to avoid
    # absent checkboxes on other tabs being misread as "false".
    tab_group_names = _TAB_GROUPS.get(tab, [])

    changed = []
    for key, meta in EDITABLE_SETTINGS.items():
        if meta["group"] not in tab_group_names:
            continue
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
        "current_tab_label": "API Tokens",
        "tab_description": _TAB_DESCRIPTIONS.get("tokens", ""),
        "section_descriptions": _SECTION_DESCRIPTIONS,
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
