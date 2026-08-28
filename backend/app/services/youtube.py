from dataclasses import dataclass
from datetime import datetime
from typing import Any
import re

import httpx

from app.services.quota import YouTubeQuotaTracker

API_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class YouTubeVideo:
    video_id: str
    title: str
    description: str
    channel_name: str
    thumbnail_url: str
    duration_seconds: int
    published_at: datetime
    view_count: int | None
    tags: list[str]


def parse_iso8601_duration(value: str) -> int:
    match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value)
    if not match:
        raise YouTubeApiError(f"Unsupported YouTube duration: {value}")
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return days * 86_400 + hours * 3600 + minutes * 60 + seconds


class YouTubeClient:
    def __init__(self, api_key: str, quota: YouTubeQuotaTracker) -> None:
        self.api_key = api_key
        self.quota = quota

    async def search_video_ids(
        self, query: str, limit: int, published_after: datetime | None = None
    ) -> list[str]:
        params = {
            "part": "snippet", "q": query, "type": "video", "maxResults": limit, "safeSearch": "moderate",
            "order": "date" if published_after else "relevance",
        }
        if published_after:
            params["publishedAfter"] = published_after.isoformat().replace("+00:00", "Z")
        data = await self._get("/search", params)
        return [item["id"]["videoId"] for item in data.get("items", []) if item.get("id", {}).get("videoId")]

    async def get_videos(self, video_ids: list[str]) -> list[YouTubeVideo]:
        if not video_ids:
            return []
        data = await self._get("/videos", {
            "part": "snippet,contentDetails,statistics", "id": ",".join(video_ids[:50]), "maxResults": 50,
        })
        return [self._parse_video(item) for item in data.get("items", [])]

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        # search.list costs 100 units; videos.list costs 1 unit per request.
        await self.quota.add_usage(100 if path == "/search" else 1)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{API_URL}{path}", params={**params, "key": self.api_key})
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            message = exc.response.json().get("error", {}).get("message", "Unknown YouTube API error")
            raise YouTubeApiError(message) from exc
        except httpx.HTTPError as exc:
            raise YouTubeApiError("YouTube API request could not be completed") from exc

    @staticmethod
    def _parse_video(item: dict[str, Any]) -> YouTubeVideo:
        snippet = item["snippet"]
        thumbnails = snippet.get("thumbnails", {})
        image = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default")
        if not image or not image.get("url"):
            raise YouTubeApiError("A video did not include a thumbnail")
        statistics = item.get("statistics", {})
        return YouTubeVideo(
            video_id=item["id"], title=snippet["title"], description=snippet.get("description", ""),
            channel_name=snippet["channelTitle"], thumbnail_url=image["url"],
            duration_seconds=parse_iso8601_duration(item["contentDetails"]["duration"]),
            published_at=datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")),
            view_count=int(statistics["viewCount"]) if "viewCount" in statistics else None,
            tags=snippet.get("tags", []),
        )
