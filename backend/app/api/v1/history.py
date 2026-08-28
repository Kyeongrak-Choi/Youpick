from typing import Any

from fastapi import APIRouter, Depends

from app.api.v1.auth import CurrentUser, get_current_user
from app.api.v1.dependencies import get_history_repository
from app.repositories.history import RecommendationHistoryRepository


router = APIRouter(prefix="/history", tags=["history"])


@router.get("/conversations")
async def list_conversations(
    user: CurrentUser = Depends(get_current_user),
    repository: RecommendationHistoryRepository = Depends(get_history_repository),
) -> list[dict[str, Any]]:
    return await repository.list_conversations(user.id)
