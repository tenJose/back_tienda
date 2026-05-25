from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Tiendita POS API"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"
    cors_allow_origins: str = (
        "http://localhost:4200,"
        "http://127.0.0.1:4200,"
        "http://localhost,"
        "http://127.0.0.1,"
        "https://localhost,"
        "capacitor://localhost,"
        "ionic://localhost"
    )

    database_url: str

    supabase_url: str
    supabase_publishable_key: str
    supabase_service_role_key: str | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_url: str | None = None

    require_role_header: bool = True
    require_auth_token: bool = True
    allow_role_header_fallback: bool = True

    gemini_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
