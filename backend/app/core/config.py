from dataclasses import dataclass
from functools import lru_cache
from os import getenv

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    youtube_api_key: str | None
    redis_url: str | None
    cache_ttl_seconds: int
    candidate_limit: int
    youtube_daily_quota_limit: int
    google_oauth_client_id: str | None
    cors_origins: list[str]
    supabase_url: str | None
    supabase_secret_key: str | None


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=getenv("APP_NAME", "YouPick API"),
        app_env=getenv("APP_ENV", "development"),
        youtube_api_key=getenv("YOUTUBE_API_KEY") or None,
        redis_url=getenv("REDIS_URL") or None,
        cache_ttl_seconds=int(getenv("RECOMMENDATION_CACHE_TTL_SECONDS", "1800")),
        candidate_limit=int(getenv("YOUTUBE_CANDIDATE_LIMIT", "50")),
        youtube_daily_quota_limit=int(getenv("YOUTUBE_DAILY_QUOTA_LIMIT", "10000")),
        google_oauth_client_id=getenv("GOOGLE_OAUTH_CLIENT_ID") or None,
        cors_origins=[
            origin.strip()
            for origin in getenv(
                "CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501"
            ).split(",")
            if origin.strip()
        ],
        supabase_url=getenv("SUPABASE_URL") or None,
        # Legacy service_role keys remain supported during Supabase's key migration.
        supabase_secret_key=(
            getenv("SUPABASE_SECRET_KEY")
            or getenv("SUPABASE_SERVICE_ROLE_KEY")
            or None
        ),
    )
