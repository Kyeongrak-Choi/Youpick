from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import FeedbackCreate


def test_feedback_accepts_a_recommendation_rating() -> None:
    feedback = FeedbackCreate(recommendation_id=uuid4(), is_helpful=True, comment="실습에 도움이 됐어요.")
    assert feedback.is_helpful is True


def test_feedback_rejects_a_too_long_comment() -> None:
    with pytest.raises(ValidationError):
        FeedbackCreate(recommendation_id=uuid4(), is_helpful=False, comment="a" * 501)
