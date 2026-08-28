"""Estimated YouTube Data API quota tracking.

The YouTube Data API does not expose an API-key's remaining daily quota in its
responses.  We therefore count the calls made by this application and present
the remaining amount against the configured daily allowance.
"""

from datetime import datetime, timedelta
from time import time
from typing import Final
from zoneinfo import ZoneInfo

from redis.asyncio import Redis


YOUTUBE_DAILY_QUOTA: Final = 10_000
PACIFIC_TIME: Final = ZoneInfo("America/Los_Angeles")


class YouTubeQuotaTracker:
    def __init__(self, redis_url: str | None, daily_limit: int = YOUTUBE_DAILY_QUOTA) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True) if redis_url else None
        self.daily_limit = daily_limit
        self._memory_day = ""
        self._memory_used = 0

    @staticmethod
    def _quota_day() -> str:
        # YouTube's daily quota is reset at midnight Pacific Time.
        return datetime.now(PACIFIC_TIME).date().isoformat()

    def _key(self) -> str:
        return f"youtube:quota:{self._quota_day()}"

    @staticmethod
    def _seconds_until_reset() -> int:
        now = datetime.now(PACIFIC_TIME)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1, int((tomorrow - now).total_seconds()))

    async def add_usage(self, units: int) -> None:
        """Count a request when it is sent; failed API requests can also consume quota."""
        if self.redis:
            try:
                key = self._key()
                used = await self.redis.incrby(key, units)
                if used == units:
                    await self.redis.expire(key, self._seconds_until_reset())
                return
            except Exception:
                # Local development remains usable if Redis is unavailable.
                pass
        day = self._quota_day()
        if self._memory_day != day:
            self._memory_day, self._memory_used = day, 0
        self._memory_used += units

    async def status(self) -> dict[str, int | str]:
        day = self._quota_day()
        used = 0
        if self.redis:
            try:
                used = int(await self.redis.get(self._key()) or 0)
            except Exception:
                pass
        if not used:
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
            "tracking": "estimated",
        }
