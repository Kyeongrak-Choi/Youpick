from functools import lru_cache

from fastapi import HTTPException, status

from app.agents.recommendation import AnalysisAgent, FilterAgent, RankingAgent, RecommendationOrchestrator, SearchAgent, VideoDetailAgent
from app.core.config import get_settings
from app.services.cache import RecommendationCache
from app.services.quota import YouTubeQuotaTracker
from app.services.youtube import YouTubeClient
from app.repositories.history import RecommendationHistoryRepository


@lru_cache
def get_youtube_quota_tracker() -> YouTubeQuotaTracker:
    settings = get_settings()
    return YouTubeQuotaTracker(settings.redis_url, settings.youtube_daily_quota_limit)


@lru_cache
def get_recommendation_orchestrator() -> RecommendationOrchestrator:
    settings = get_settings()
    if not settings.youtube_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YOUTUBE_API_KEY is not configured. Add it to backend/.env.")
    youtube = YouTubeClient(settings.youtube_api_key, get_youtube_quota_tracker())
    history = (
        RecommendationHistoryRepository(settings.supabase_url, settings.supabase_secret_key)
        if settings.supabase_url and settings.supabase_secret_key
        else None
    )
    return RecommendationOrchestrator(SearchAgent(youtube, settings.candidate_limit), VideoDetailAgent(youtube),
        FilterAgent(), AnalysisAgent(), RankingAgent(), RecommendationCache(settings.redis_url), settings.cache_ttl_seconds,
        history)


@lru_cache
def get_history_repository() -> RecommendationHistoryRepository:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase is not configured. Add SUPABASE_URL and SUPABASE_SECRET_KEY to backend/.env.",
        )
    return RecommendationHistoryRepository(settings.supabase_url, settings.supabase_secret_key)
