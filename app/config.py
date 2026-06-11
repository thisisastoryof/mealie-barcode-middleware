from pydantic_settings import BaseSettings


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


settings = Settings()
