"""Estimated YouTube Data API quota tracking.

The YouTube Data API does not expose an API-key's remaining daily quota in its
responses.  We therefore count the calls made by this application and present
the remaining amount against the configured daily allowance.
"""

from datetime import datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo

import httpx


YOUTUBE_DAILY_QUOTA: Final = 10_000
PACIFIC_TIME: Final = ZoneInfo("America/Los_Angeles")


class YouTubeQuotaTracker:
    def __init__(self, supabase_url: str | None, supabase_secret_key: str | None,
                 daily_limit: int = YOUTUBE_DAILY_QUOTA) -> None:
        self._base_url = f"{supabase_url.rstrip('/')}/rest/v1" if supabase_url else None
        self._headers = (
            {
                "apikey": supabase_secret_key,
                "Authorization": f"Bearer {supabase_secret_key}",
                "Content-Type": "application/json",
            }
            if supabase_secret_key else None
        )
        self.daily_limit = daily_limit
        self._memory_day = ""
        self._memory_used = 0

    @staticmethod
    def _quota_day() -> str:
        # YouTube's daily quota is reset at midnight Pacific Time.
        return datetime.now(PACIFIC_TIME).date().isoformat()

    @staticmethod
    def _seconds_until_reset() -> int:
        now = datetime.now(PACIFIC_TIME)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1, int((tomorrow - now).total_seconds()))

    async def add_usage(self, units: int) -> None:
        """Count a request when it is sent; failed API requests can also consume quota."""
        if self._base_url and self._headers:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.post(
                        f"{self._base_url}/rpc/increment_youtube_api_quota",
                        headers=self._headers,
                        json={"usage_day": self._quota_day(), "added_units": units},
                    )
                    response.raise_for_status()
                return
            except Exception:
                # Recommendations should still work if quota persistence is temporarily unavailable.
                pass
        day = self._quota_day()
        if self._memory_day != day:
            self._memory_day, self._memory_used = day, 0
        self._memory_used += units

    async def status(self) -> dict[str, int | str]:
        day = self._quota_day()
        used = 0
        tracking = "memory_fallback"
        if self._base_url and self._headers:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(
                        f"{self._base_url}/youtube_api_quota_daily",
                        headers=self._headers,
                        params={"quota_day": f"eq.{day}", "select": "used_units"},
                    )
                    response.raise_for_status()
                    rows = response.json()
                    used = int(rows[0]["used_units"]) if rows else 0
                    tracking = "supabase"
            except Exception:
                pass
        if tracking != "supabase":
            if self._memory_day != day:
                self._memory_day, self._memory_used = day, 0
            used = self._memory_used
        remaining = max(0, self.daily_limit - used)
        return {
            "daily_limit": self.daily_limit,
            "used_units": used,
            "remaining_units": remaining,
            "quota_day": day,
            "resets_at": (datetime.now(PACIFIC_TIME) + timedelta(seconds=self._seconds_until_reset())).isoformat(),
            "tracking": tracking,
        }
