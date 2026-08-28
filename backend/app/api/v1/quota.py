from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_youtube_quota_tracker
from app.services.quota import YouTubeQuotaTracker


router = APIRouter(prefix="/quota", tags=["quota"])


@router.get("/youtube")
async def youtube_quota_status(
    tracker: YouTubeQuotaTracker = Depends(get_youtube_quota_tracker),
) -> dict[str, int | str]:
    """Return the app's estimated YouTube daily quota usage."""
    return await tracker.status()
