from __future__ import annotations

import time

import redis.asyncio as redis


class RateLimiter:
    """Fixed-window per-minute limiter backed by Redis INCR + EXPIRE."""

    def __init__(
        self,
        client: redis.Redis,
        *,
        anonymous_per_minute: int,
        with_key_per_minute: int,
    ) -> None:
        self._r = client
        self._anon = anonymous_per_minute
        self._auth = with_key_per_minute

    async def check(
        self, *, identifier: str, is_authenticated: bool, override: int | None = None,
    ) -> bool:
        base = self._auth if is_authenticated else self._anon
        limit = override if override is not None else base
        bucket = int(time.time() // 60)
        key = f"rl:{identifier}:{bucket}"
        pipe = self._r.pipeline()
        pipe.incr(key)
        pipe.expire(key, 90)  # 60s window + 30s grace
        count, _ = await pipe.execute()
        return count <= limit
