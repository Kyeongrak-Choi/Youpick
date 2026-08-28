from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ViewingPurpose(StrEnum):
    SUMMARY = "summary"
    CONCEPT = "concept"
    DEEP_DIVE = "deep_dive"
    PRACTICE = "practice"


class RecommendationRequest(BaseModel):
    category: str = Field(min_length=1, max_length=50)
    detail_request: str = Field(min_length=3, max_length=300)
    max_duration_minutes: int | None = Field(default=None, ge=1, le=240)
    purpose: str = Field(min_length=1, max_length=50)


class RecommendedVideo(BaseModel):
    recommendation_id: UUID | None = None
    video_id: str
    title: str
    channel_name: str
    thumbnail_url: HttpUrl
    duration_seconds: int
    published_at: datetime
    view_count: int | None = None
    tags: list[str] = Field(default_factory=list)
    relevance_score: float = Field(ge=0, le=100)
    recommendation_reason: str


class RecommendationResponse(BaseModel):
    request: RecommendationRequest
    recommendations: list[RecommendedVideo]
    candidate_count: int
    filtered_count: int
    cached: bool
    generated_at: datetime
