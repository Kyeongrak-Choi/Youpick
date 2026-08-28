from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    recommendation_id: UUID
    is_helpful: bool
    comment: str | None = Field(default=None, max_length=500)


class FeedbackResponse(BaseModel):
    id: UUID
    recommendation_id: UUID
    is_helpful: bool
    comment: str | None
    created_at: datetime
