from __future__ import annotations

import json
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
        await self._redis.set(key, json.dumps(value), ex=ttl or self._default_ttl)

    async def ttl(self, key: str) -> int:
        return await self._redis.ttl(key)

    async def ping(self) -> bool:
        try:
            return await self._redis.ping()
        except (redis.RedisError, OSError):
            return False

    @staticmethod
    def convert_key(service: str, type_: str, id_: str) -> str:
        return f"cache:{service}:{type_}:{id_}"
