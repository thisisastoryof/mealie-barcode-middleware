import json
from datetime import timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

from app.config import settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_tz = ZoneInfo(settings.timezone)


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
