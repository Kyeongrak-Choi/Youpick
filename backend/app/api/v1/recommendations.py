from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID

from app.agents.recommendation import RecommendationOrchestrator
from app.api.v1.dependencies import get_recommendation_orchestrator
from app.api.v1.auth import CurrentUser, get_current_user
from app.schemas import RecommendationRequest, RecommendationResponse
from app.services.youtube import YouTubeApiError

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationResponse)
async def create_recommendations(request: RecommendationRequest,
    conversation_id: UUID | None = None,
    orchestrator: RecommendationOrchestrator = Depends(get_recommendation_orchestrator),
    user: CurrentUser = Depends(get_current_user)) -> RecommendationResponse:
    try:
        return await orchestrator.recommend(request, user.id, user.email, conversation_id)
    except YouTubeApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
