import hashlib
import json
from datetime import timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

from app.config import settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_tz = ZoneInfo(settings.timezone)

# Cache-buster: short hash of JS/CSS modification times (recomputed on startup)
_static_dir = BASE_DIR / "static"
_mtimes = "".join(
    str(f.stat().st_mtime_ns)
    for f in sorted(_static_dir.rglob("*.js"))
    if f.is_file()
)
_mtimes += "".join(
    str(f.stat().st_mtime_ns)
    for f in sorted(_static_dir.rglob("*.css"))
    if f.is_file()
)
ASSET_VERSION = hashlib.md5(_mtimes.encode()).hexdigest()[:8]


def _localtime(value, fmt="%Y-%m-%d %H:%M"):
    """Jinja2 filter: convert a UTC datetime to the configured local timezone."""
    if not value:
        return "\u2014"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_tz).strftime(fmt)


def _fromjson(value):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


templates.env.filters["localtime"] = _localtime
templates.env.filters["fromjson"] = _fromjson
templates.env.globals["v"] = ASSET_VERSION
