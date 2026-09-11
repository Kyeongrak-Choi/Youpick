from typing import Any

from fastapi import APIRouter, Depends

from app.api.v1.auth import CurrentUser, get_current_user
from app.api.v1.dependencies import get_history_repository, get_youtube_quota_tracker
from app.repositories.history import RecommendationHistoryRepository
from app.services.quota import YouTubeQuotaTracker


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def dashboard_overview(
    _: CurrentUser = Depends(get_current_user),
    repository: RecommendationHistoryRepository = Depends(get_history_repository),
    quota_tracker: YouTubeQuotaTracker = Depends(get_youtube_quota_tracker),
) -> dict[str, Any]:
    """Return project-wide metrics for the signed-in dashboard."""
    overview = await repository.dashboard_overview()
    overview["quota"] = await quota_tracker.status()
    return overview
