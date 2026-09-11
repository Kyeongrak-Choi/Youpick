from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.auth import CurrentUser, get_current_user
from app.api.v1.dependencies import get_history_repository
from app.repositories.history import RecommendationHistoryRepository
from app.schemas import FeedbackCreate, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    feedback: FeedbackCreate,
    repository: RecommendationHistoryRepository = Depends(get_history_repository),
) -> FeedbackResponse:
    try:
        return await repository.save_feedback(feedback)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/choices", response_model=dict[str, bool])
async def get_feedback_choices(
    recommendation_ids: list[UUID] = Query(default=[]),
    _user: CurrentUser = Depends(get_current_user),
    repository: RecommendationHistoryRepository = Depends(get_history_repository),
) -> dict[str, bool]:
    """Restore the feedback selection shown for saved recommendation cards."""
    try:
        return await repository.feedback_choices(recommendation_ids)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
