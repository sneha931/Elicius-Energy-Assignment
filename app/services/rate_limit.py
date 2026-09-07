import time

from redis.asyncio import Redis

from app.core.config import settings


class RateLimiter:
    def __init__(self):
        self.redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    async def is_allowed(
        self,
        user_id: int,
        limit: int = 30,
        window_seconds: int = 60,
    ) -> bool:

        current_window = int(time.time() // window_seconds)

        key = f"rate_limit:{user_id}:{current_window}"

        count = await self.redis.incr(key)

        if count == 1:
            await self.redis.expire(key, window_seconds)

        print(f"RATE LIMIT: key={key}, count={count}, limit={limit}")

        return count <= limit


rate_limiter = RateLimiter()