import json
from hashlib import sha256
from time import time
from typing import Any

from redis.asyncio import Redis


class RecommendationCache:
    def __init__(self, redis_url: str | None) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True) if redis_url else None
        self.memory: dict[str, tuple[float, dict[str, Any]]] = {}

    @staticmethod
    def key_for(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return f"recommendations:{sha256(raw.encode()).hexdigest()}"

    async def get(self, key: str) -> dict[str, Any] | None:
        if self.redis:
            try:
                value = await self.redis.get(key)
                if value:
                    return json.loads(value)
            except Exception:
                pass
        item = self.memory.get(key)
        if not item or item[0] <= time():
            self.memory.pop(key, None)
            return None
        return item[1]

    async def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        if self.redis:
            try:
                await self.redis.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
                return
            except Exception:
                pass
        self.memory[key] = (time() + ttl_seconds, value)
