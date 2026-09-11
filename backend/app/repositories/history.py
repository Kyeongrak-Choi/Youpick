"""Supabase REST repository for recommendation history.

The repository is optional: recommendation delivery must not fail merely because
analytics/history storage is unavailable.
"""

import logging
from typing import Any
from uuid import UUID
from datetime import UTC, datetime

import httpx

from app.schemas import FeedbackCreate, FeedbackResponse, RecommendationResponse

logger = logging.getLogger(__name__)


class RecommendationHistoryRepository:
    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self._base_url = f"{supabase_url.rstrip('/')}/rest/v1"
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def save(self, response: RecommendationResponse, user_id: str | None = None,
                   user_email: str | None = None, conversation_id: UUID | None = None) -> dict[int, UUID]:
        """Save a response and return its Supabase recommendation IDs by rank."""
        request = response.request
        search_request = {
            "category": request.category,
            "detail_request": request.detail_request,
            "max_duration_minutes": request.max_duration_minutes,
            "purpose": request.purpose,
            "candidate_count": response.candidate_count,
            "filtered_count": response.filtered_count,
            "cached": response.cached,
            "user_id": user_id,
            "conversation_id": str(conversation_id) if conversation_id else None,
        }
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                if user_id and conversation_id:
                    conversation = {
                        "id": str(conversation_id), "user_id": user_id, "user_email": user_email,
                        "title": request.detail_request.replace("\n", " ")[:80],
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                    created_conversation = await client.post(
                        f"{self._base_url}/conversations?on_conflict=id",
                        headers={**self._headers, "Prefer": "resolution=merge-duplicates,return=representation"},
                        json=conversation,
                    )
                    created_conversation.raise_for_status()
                created = await client.post(
                    f"{self._base_url}/search_requests",
                    headers=self._headers,
                    json=search_request,
                )
                created.raise_for_status()
                request_id = created.json()[0]["id"]
                rows = [
                    self._recommendation_row(request_id, index + 1, item.model_dump(mode="json"))
                    for index, item in enumerate(response.recommendations)
                ]
                if rows:
                    inserted = await client.post(
                        f"{self._base_url}/recommendations",
                        headers=self._headers,
                        json=rows,
                    )
                    inserted.raise_for_status()
                    return {row["rank"]: UUID(row["id"]) for row in inserted.json()}
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            logger.warning("Unable to save YouPick recommendation history: %s", exc)
        return {}

    async def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        """Return this account's conversations with enough data to reopen a result."""
        params = {
            "user_id": f"eq.{user_id}",
            "select": (
                "id,title,created_at,updated_at,"
                "search_requests(id,category,detail_request,max_duration_minutes,purpose,"
                "candidate_count,filtered_count,cached,created_at,"
                "recommendations(id,video_id,title,channel_name,thumbnail_url,duration_seconds,"
                "published_at,view_count,tags,relevance_score,recommendation_reason,short_review,rank))"
            ),
            "order": "updated_at.desc",
        }
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._base_url}/conversations", headers=self._headers, params=params)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, TypeError) as exc:
            logger.warning("Unable to load YouPick conversation history: %s", exc)
            return []

    async def dashboard_overview(self) -> dict[str, Any]:
        """Load project-wide aggregate metrics calculated inside Supabase."""
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(
                    f"{self._base_url}/rpc/get_youpick_dashboard", headers=self._headers, json={}
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, TypeError) as exc:
            logger.warning("Unable to load YouPick dashboard overview: %s", exc)
            raise RuntimeError("대시보드 데이터를 불러올 수 없습니다.") from exc

    async def save_feedback(self, feedback: FeedbackCreate) -> FeedbackResponse:
        """Persist one anonymous usefulness rating for a shown recommendation."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{self._base_url}/feedback",
                    headers=self._headers,
                    json=feedback.model_dump(mode="json"),
                )
                response.raise_for_status()
                return FeedbackResponse.model_validate(response.json()[0])
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Unable to save recommendation feedback") from exc

    async def feedback_choices(self, recommendation_ids: list[UUID]) -> dict[str, bool]:
        """Return the most recent saved choice for each displayed recommendation."""
        if not recommendation_ids:
            return {}
        params = {
            "select": "recommendation_id,is_helpful,created_at",
            "recommendation_id": f"in.({','.join(str(item) for item in recommendation_ids)})",
            "order": "created_at.desc",
        }
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._base_url}/feedback", headers=self._headers, params=params)
                response.raise_for_status()
                choices: dict[str, bool] = {}
                for row in response.json():
                    # The rows are newest-first. Keep the first response when older
                    # duplicate feedback exists from before choices were restored.
                    choices.setdefault(row["recommendation_id"], row["is_helpful"])
                return choices
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            logger.warning("Unable to load recommendation feedback choices: %s", exc)
            raise RuntimeError("저장한 피드백을 불러올 수 없습니다.") from exc

    @staticmethod
    def _recommendation_row(
        search_request_id: str, rank: int, item: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "search_request_id": search_request_id,
            "video_id": item["video_id"],
            "title": item["title"],
            "channel_name": item["channel_name"],
            "thumbnail_url": str(item["thumbnail_url"]),
            "duration_seconds": item["duration_seconds"],
            "published_at": item["published_at"],
            "view_count": item["view_count"],
            "tags": item["tags"],
            "relevance_score": item["relevance_score"],
            "recommendation_reason": item["recommendation_reason"],
            "short_review": item.get("short_review"),
            "rank": rank,
        }
