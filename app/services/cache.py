import hashlib
import json

from redis.asyncio import Redis

from app.core.config import settings


class CacheService:
    def __init__(self):
        self.redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    def _make_key(self, question: str) -> str:
        normalized = question.strip().lower()
        question_hash = hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

        return f"chat:{question_hash}"

    async def get(self, question: str):
        key = self._make_key(question)

        cached = await self.redis.get(key)

        if cached is None:
            return None

        return json.loads(cached)

    async def set(self, question: str, result: dict, ttl: int = 300):
        key = self._make_key(question)

        await self.redis.set(
            key,
            json.dumps(result),
            ex=ttl,
        )

    async def close(self):
        await self.redis.aclose()


cache_service = CacheService()