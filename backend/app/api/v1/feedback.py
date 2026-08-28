from fastapi import APIRouter, Depends, HTTPException, status

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
