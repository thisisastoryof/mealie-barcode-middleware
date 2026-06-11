import logging
from typing import Any

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    mealie_url: str
    mealie_api_key: str
    mealie_shopping_list_id: str

    off_enabled: bool = True
    off_url_base: str = "https://world.openfoodfacts.org/api/v2/product/"
    upcdb_enabled: bool = False
    upcdb_url_base: str = "https://api.upcdatabase.org/product/"
    upcdb_api_key: str | None = None

    lookup_strategy: str = "failover"   # failover | complement
    lookup_primary: str = "off"          # off | upcdb
    lookup_enrich_in_background: bool = True  # complement: secondary call after response

    item_sync_interval_hours: int = 6
    fuzzy_match_threshold: int = 85
    fuzzy_ambiguity_gap: int = 10
    lookup_ttl_days: int = 30
    max_retry_attempts: int = 10

    middleware_base_url: str = ""

    db_path: str = "/data/barcode.db"
    timezone: str = "Europe/Berlin"
    port: int = 8000
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# ── Editable settings registry ──────────────────────────────────────
# Each entry: field_name → {type, description, choices (optional)}
# Only settings listed here can be changed via the web UI.

EDITABLE_SETTINGS: dict[str, dict[str, Any]] = {
    # Barcode Lookup Sources
    "off_enabled": {
        "type": "bool",
        "label": "OFF_ENABLED",
        "description": "Use Open Food Facts for barcode lookups",
        "group": "Barcode Lookup Sources",
    },
    "upcdb_enabled": {
        "type": "bool",
        "label": "UPCDB_ENABLED",
        "description": "Use UPC Database as fallback lookup source",
        "group": "Barcode Lookup Sources",
    },
    "lookup_strategy": {
        "type": "choice",
        "label": "LOOKUP_STRATEGY",
        "description": "failover = secondary only when primary returns nothing; complement = fill gaps from secondary",
        "choices": ["failover", "complement"],
        "group": "Barcode Lookup Sources",
    },
    "lookup_primary": {
        "type": "choice",
        "label": "LOOKUP_PRIMARY",
        "description": "Which API is tried first",
        "choices": ["off", "upcdb"],
        "group": "Barcode Lookup Sources",
    },
    "lookup_enrich_in_background": {
        "type": "bool",
        "label": "LOOKUP_ENRICH_IN_BACKGROUND",
        "description": "complement mode: secondary call runs after ESP32 response (faster scans)",
        "group": "Barcode Lookup Sources",
    },
    # Matching & Sync
    "fuzzy_match_threshold": {
        "type": "int",
        "label": "FUZZY_MATCH_THRESHOLD",
        "description": "Minimum score (0–100) to accept a fuzzy item match",
        "min": 0,
        "max": 100,
        "group": "Matching & Sync",
    },
    "fuzzy_ambiguity_gap": {
        "type": "int",
        "label": "FUZZY_AMBIGUITY_GAP",
        "description": "Min. score gap between top two matches to avoid ambiguity",
        "min": 0,
        "max": 50,
        "group": "Matching & Sync",
    },
    "item_sync_interval_hours": {
        "type": "int",
        "label": "ITEM_SYNC_INTERVAL_HOURS",
        "description": "How often the Mealie item list is re-synced (hours)",
        "min": 1,
        "max": 168,
        "group": "Matching & Sync",
    },
    "lookup_ttl_days": {
        "type": "int",
        "label": "LOOKUP_TTL_DAYS",
        "description": "Days before a cached barcode lookup expires",
        "min": 1,
        "max": 365,
        "group": "Matching & Sync",
    },
    "max_retry_attempts": {
        "type": "int",
        "label": "MAX_RETRY_ATTEMPTS",
        "description": "Max retries before a queued item is marked as failed",
        "min": 1,
        "max": 100,
        "group": "Matching & Sync",
    },
    # System
    "timezone": {
        "type": "str",
        "label": "TIMEZONE",
        "description": "Timezone used for timestamps and scheduling (IANA)",
        "group": "System",
    },
    "middleware_base_url": {
        "type": "str",
        "label": "MIDDLEWARE_BASE_URL",
        "description": "Base URL for deep links in HA notifications",
        "group": "System",
    },
    "log_level": {
        "type": "choice",
        "label": "LOG_LEVEL",
        "description": "Application log verbosity",
        "choices": ["DEBUG", "INFO", "WARNING", "ERROR"],
        "group": "System",
    },
}

# Settings that are NEVER editable via the UI (secrets, paths, ports)
READONLY_SETTINGS: dict[str, dict[str, Any]] = {
    "mealie_url": {
        "label": "MEALIE_URL",
        "description": "Base URL of your Mealie instance",
        "group": "Mealie Connection",
    },
    "mealie_shopping_list_id": {
        "label": "MEALIE_SHOPPING_LIST_ID",
        "description": "Shopping list where scanned items are added",
        "group": "Mealie Connection",
    },
    "mealie_api_key": {
        "label": "MEALIE_API_KEY",
        "description": "Mealie API token",
        "group": "Mealie Connection",
        "secret": True,
    },
    "off_url_base": {
        "label": "OFF_URL_BASE",
        "description": "Open Food Facts API endpoint",
        "group": "Barcode Lookup Sources",
    },
    "upcdb_url_base": {
        "label": "UPCDB_URL_BASE",
        "description": "UPC Database API endpoint",
        "group": "Barcode Lookup Sources",
    },
    "upcdb_api_key": {
        "label": "UPCDB_API_KEY",
        "description": "API key for UPC Database",
        "group": "Barcode Lookup Sources",
        "secret": True,
    },
    "db_path": {
        "label": "DB_PATH",
        "description": "Path to the SQLite database file",
        "group": "System",
    },
    "port": {
        "label": "PORT",
        "description": "HTTP port the middleware listens on",
        "group": "System",
    },
}


class SettingsManager:
    """Proxy that overlays DB overrides on top of Pydantic env settings.

    All existing ``settings.X`` attribute access works unchanged.
    DB overrides are loaded once at init and refreshed on save.
    """

    def __init__(self, env_settings: Settings):
        # Store via __dict__ to avoid triggering __setattr__
        self.__dict__["_env"] = env_settings
        self.__dict__["_overrides"] = {}

    # ── attribute access: override → env fallback ──
    def __getattr__(self, name: str) -> Any:
        if name in self.__dict__.get("_overrides", {}):
            return self._overrides[name]
        return getattr(self._env, name)

    def __setattr__(self, name: str, value: Any):
        raise AttributeError("Use save_override() to change settings")

    # ── override management ──
    def load_overrides_from_db(self) -> None:
        """Load all overrides from the settings_overrides table."""
        from app.database import SessionLocal
        from app.models import SettingsOverride

        db = SessionLocal()
        try:
            rows = db.query(SettingsOverride).all()
            overrides = {}
            for row in rows:
                if row.key in EDITABLE_SETTINGS:
                    overrides[row.key] = self._coerce(row.key, row.value)
            self.__dict__["_overrides"] = overrides
            if overrides:
                logger.info("Loaded %d settings override(s) from DB: %s",
                            len(overrides), ", ".join(overrides.keys()))
        finally:
            db.close()

    def save_override(self, key: str, value: str, db) -> None:
        """Save a single override to the DB and update in-memory cache.

        If the new value matches the env default, the override is removed
        instead — keeping the DB clean and the UI consistent.
        """
        from app.models import SettingsOverride
        from app.utils import utcnow

        if key not in EDITABLE_SETTINGS:
            raise ValueError(f"Setting '{key}' is not editable")

        coerced = self._coerce(key, value)
        env_default = getattr(self._env, key)

        # Value matches env default → remove any existing override
        if coerced == env_default:
            self.reset_override(key, db)
            return

        existing = db.get(SettingsOverride, key)
        if existing:
            existing.value = str(value)
            existing.updated_at = utcnow()
        else:
            db.add(SettingsOverride(key=key, value=str(value)))
        db.commit()

        self.__dict__["_overrides"][key] = coerced

    def reset_override(self, key: str, db) -> None:
        """Remove a DB override, reverting to the env/default value."""
        from app.models import SettingsOverride

        existing = db.get(SettingsOverride, key)
        if existing:
            db.delete(existing)
            db.commit()

        self.__dict__["_overrides"].pop(key, None)

    def is_overridden(self, key: str) -> bool:
        """True if this setting has a DB override (vs env default)."""
        return key in self.__dict__.get("_overrides", {})

    def get_env_default(self, key: str) -> Any:
        """Get the original env/default value (ignoring DB overrides)."""
        return getattr(self._env, key)

    def get_display_value(self, key: str) -> str:
        """Get the current effective value as a display string."""
        val = getattr(self, key)
        if val is None:
            return ""
        return str(val)

    def _coerce(self, key: str, raw: str) -> Any:
        """Coerce a string value to the correct Python type."""
        meta = EDITABLE_SETTINGS[key]
        field_type = meta["type"]
        if field_type == "bool":
            return raw.lower() in ("true", "1", "yes", "on")
        if field_type == "int":
            v = int(raw)
            if "min" in meta:
                v = max(meta["min"], v)
            if "max" in meta:
                v = min(meta["max"], v)
            return v
        if field_type == "choice":
            if raw not in meta["choices"]:
                raise ValueError(f"Invalid choice '{raw}' for {key}")
            return raw
        return raw  # str


_env_settings = Settings()
settings = SettingsManager(_env_settings)
