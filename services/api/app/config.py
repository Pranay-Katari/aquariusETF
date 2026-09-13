from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_mode: str = "demo"
    database_url: str = f"sqlite:///{ROOT}/data/aquarius.db"
    data_dir: Path = ROOT / "data"
    redis_url: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = ""
    market_data_provider: str = "synthetic"
    market_data_api_key: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    research_provider: str = "curated"
    llm_api_key: str = ""
    llm_model: str = ""
    paper_owner_user_id: str = ""
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    paper_trading_enabled: bool = False


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
if settings.app_mode not in ("demo", "production"):
    raise RuntimeError("APP_MODE must be demo or production")
if settings.app_mode == "production" and (
    not settings.supabase_url
    or not settings.supabase_anon_key
    or settings.database_url.startswith("sqlite")
):
    raise RuntimeError(
        "Production requires Supabase Auth and PostgreSQL; demo auth is disabled."
    )
