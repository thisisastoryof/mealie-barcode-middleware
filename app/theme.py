"""Theme settings — global appearance stored in the DB."""

import logging

from app.models import SettingsOverride
from app.utils import utcnow

logger = logging.getLogger(__name__)

# Theme key prefix in the settings_overrides table
_PREFIX = "theme_"

# Defaults matching Tabler's out-of-the-box look
THEME_DEFAULTS = {
    "mode": "light",           # light | dark
    "color": "blue",           # Tabler accent colors
    "font": "sans-serif",      # sans-serif | serif | monospace | comic
    "base": "gray",            # slate | gray | zinc | neutral | stone
    "radius": "1",             # 0 | 0.5 | 1 | 1.5 | 2
}

# Valid choices for each setting
THEME_CHOICES = {
    "mode": ["light", "dark"],
    "color": [
        "blue", "azure", "indigo", "purple", "pink", "red",
        "orange", "yellow", "lime", "green", "teal", "cyan",
    ],
    "font": ["sans-serif", "serif", "monospace", "comic"],
    "base": ["slate", "gray", "zinc", "neutral", "stone"],
    "radius": ["0", "0.5", "1", "1.5", "2"],
}

# ── CSS custom-property lookup maps ─────────────────────────────────────────
# These map the user-facing choice names to the CSS values that override
# Tabler's :root custom properties.

# Accent color → hex, RGB triplet, and a 90% darkened hex
COLOR_CSS = {
    "blue":   {"hex": "#066fd1", "rgb": "6,111,209"},
    "azure":  {"hex": "#4299e1", "rgb": "66,153,225"},
    "indigo": {"hex": "#4263eb", "rgb": "66,99,235"},
    "purple": {"hex": "#ae3ec9", "rgb": "174,62,201"},
    "pink":   {"hex": "#d6336c", "rgb": "214,51,108"},
    "red":    {"hex": "#d63939", "rgb": "214,57,57"},
    "orange": {"hex": "#f76707", "rgb": "247,103,7"},
    "yellow": {"hex": "#f59f00", "rgb": "245,159,0"},
    "lime":   {"hex": "#74b816", "rgb": "116,184,22"},
    "green":  {"hex": "#2fb344", "rgb": "47,179,68"},
    "teal":   {"hex": "#0ca678", "rgb": "12,166,120"},
    "cyan":   {"hex": "#17a2b8", "rgb": "23,162,184"},
}

# Font family stacks as defined in Tabler's :root
FONT_CSS = {
    "sans-serif": '"Inter Var",Inter,-apple-system,BlinkMacSystemFont,San Francisco,Segoe UI,Roboto,Helvetica Neue,sans-serif',
    "serif":      "Georgia,Times New Roman,times,serif",
    "monospace":  "Monaco,Consolas,Liberation Mono,Courier New,monospace",
    "comic":      "Comic Sans MS,Comic Sans,Chalkboard SE,Comic Neue,sans-serif,cursive",
}

# Gray base palettes (50–950).  "gray" is Tabler's default; others from Tailwind.
GRAY_CSS = {
    "gray": None,  # Default — no overrides needed
    "slate":   {"50":"#f8fafc","100":"#f1f5f9","200":"#e2e8f0","300":"#cbd5e1","400":"#94a3b8","500":"#64748b","600":"#475569","700":"#334155","800":"#1e293b","900":"#0f172a","950":"#020617"},
    "zinc":    {"50":"#fafafa","100":"#f4f4f5","200":"#e4e4e7","300":"#d4d4d8","400":"#a1a1aa","500":"#71717a","600":"#52525b","700":"#3f3f46","800":"#27272a","900":"#18181b","950":"#09090b"},
    "neutral": {"50":"#fafafa","100":"#f5f5f5","200":"#e5e5e5","300":"#d4d4d4","400":"#a3a3a3","500":"#737373","600":"#525252","700":"#404040","800":"#262626","900":"#171717","950":"#0a0a0a"},
    "stone":   {"50":"#fafaf9","100":"#f5f5f4","200":"#e7e5e4","300":"#d6d3d1","400":"#a8a29e","500":"#78716c","600":"#57534e","700":"#44403c","800":"#292524","900":"#1c1917","950":"#0c0a09"},
}


def get_theme(db) -> dict[str, str]:
    """Return the current theme as a plain dict, filling in defaults."""
    rows = db.query(SettingsOverride).filter(
        SettingsOverride.key.startswith(_PREFIX)
    ).all()
    overrides = {row.key[len(_PREFIX):]: row.value for row in rows}
    return {k: overrides.get(k, v) for k, v in THEME_DEFAULTS.items()}


def save_theme(db, values: dict[str, str]) -> list[str]:
    """Save theme values to the DB. Returns list of changed keys."""
    changed = []
    current = get_theme(db)

    for key, default in THEME_DEFAULTS.items():
        new_val = values.get(key, default)

        # Validate
        if key in THEME_CHOICES and new_val not in THEME_CHOICES[key]:
            continue

        if new_val == current.get(key):
            continue

        db_key = f"{_PREFIX}{key}"
        existing = db.get(SettingsOverride, db_key)

        if new_val == default:
            # Remove override — back to default
            if existing:
                db.delete(existing)
            changed.append(key)
        else:
            if existing:
                existing.value = new_val
                existing.updated_at = utcnow()
            else:
                db.add(SettingsOverride(key=db_key, value=new_val))
            changed.append(key)

    if changed:
        db.commit()
        logger.info("Theme updated: %s", ", ".join(changed))

    return changed


def build_theme_css(theme: dict[str, str]) -> str:
    """Build a CSS string of :root custom-property overrides for the theme.

    Returns an empty string when every setting is at its Tabler default.
    """
    props: list[str] = []
    dark_props: list[str] = []

    # Accent color
    color = theme.get("color", THEME_DEFAULTS["color"])
    if color != THEME_DEFAULTS["color"] and color in COLOR_CSS:
        c = COLOR_CSS[color]
        props.append(f"--tblr-primary:{c['hex']}")
        props.append(f"--tblr-primary-rgb:{c['rgb']}")

    # Font family
    font = theme.get("font", THEME_DEFAULTS["font"])
    if font != THEME_DEFAULTS["font"] and font in FONT_CSS:
        props.append(f"--tblr-body-font-family:{FONT_CSS[font]}")

    # Gray base
    base = theme.get("base", THEME_DEFAULTS["base"])
    if base != THEME_DEFAULTS["base"] and base in GRAY_CSS:
        grays = GRAY_CSS[base]
        if grays:
            for step, val in grays.items():
                props.append(f"--tblr-gray-{step}:{val}")
            # Dark mode maps specific gray steps to body/surface colors
            dark_props.append(f"--tblr-body-color:{grays['200']}")
            dark_props.append(f"--tblr-body-bg:{grays['900']}")
            dark_props.append(f"--tblr-secondary-bg:{grays['800']}")
            dark_props.append(f"--tblr-light-text-emphasis:{grays['100']}")
            dark_props.append(f"--tblr-dark-text-emphasis:{grays['300']}")
            dark_props.append(f"--tblr-light-bg-subtle:{grays['800']}")

    # Border radius scale
    radius = theme.get("radius", THEME_DEFAULTS["radius"])
    if radius != THEME_DEFAULTS["radius"]:
        props.append(f"--tblr-border-radius-scale:{radius}")

    if not props and not dark_props:
        return ""
    parts = []
    if props:
        parts.append(":root{" + ";".join(props) + "}")
    if dark_props:
        parts.append("[data-bs-theme=dark]{" + ";".join(dark_props) + "}")
    return "".join(parts)
