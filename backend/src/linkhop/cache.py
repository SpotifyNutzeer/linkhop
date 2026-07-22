from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

import redis.asyncio as redis


class Cache:
    def __init__(self, client: redis.Redis, default_ttl: int) -> None:
        self._redis = client
        self._default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ex = ttl if ttl is not None else self._default_ttl
        await self._redis.set(key, json.dumps(value), ex=ex)

    async def ttl(self, key: str) -> int:
        return await self._redis.ttl(key)

    async def ping(self) -> bool:
        try:
            # redis-py typed `ping()` als Awaitable[bool] | bool (sync/async
            # Stub-Union). Im asyncio-Client ist es immer Awaitable.
            return await self._redis.ping()  # type: ignore[misc]
        except (redis.RedisError, OSError):
            return False

    @staticmethod
    def convert_key(services: Iterable[str], service: str, type_: str, id_: str) -> str:
        # Der aktive Dienste-Satz ist Teil des Keys: Einträge, die unter einem
        # anderen Satz berechnet wurden (Dienst aktiviert/deaktiviert), würden
        # sonst bis zu TTL lang veraltete Target-Listen ausliefern.
        fingerprint = "+".join(sorted(services))
        return f"cache:{fingerprint}:{service}:{type_}:{id_}"
