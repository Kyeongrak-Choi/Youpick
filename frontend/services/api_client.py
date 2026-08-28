"""HTTP client for the YouPick FastAPI service."""

from typing import Any

import httpx


class YouPickApiError(RuntimeError):
    pass


class YouPickApiClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def recommend(self, payload: dict[str, Any], id_token: str, conversation_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/recommendations?conversation_id={conversation_id}", payload, id_token)

    def send_feedback(self, payload: dict[str, Any], id_token: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/feedback", payload, id_token)

    def youtube_quota(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/quota/youtube", None)

    def conversations(self, id_token: str) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/history/conversations", None, id_token)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None,
                 id_token: str | None = None) -> Any:
        try:
            headers = {"Authorization": f"Bearer {id_token}"} if id_token else None
            response = httpx.request(method, f"{self._base_url}{path}", json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail", exc.response.text)
            except ValueError:
                detail = exc.response.text
            raise YouPickApiError(str(detail)) from exc
        except httpx.HTTPError as exc:
            raise YouPickApiError("백엔드에 연결할 수 없습니다. FastAPI 실행 상태와 주소를 확인해 주세요.") from exc
