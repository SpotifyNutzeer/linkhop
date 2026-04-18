import fakeredis.aioredis
import pytest

from linkhop.cache import Cache


@pytest.fixture
async def cache():
    client = fakeredis.aioredis.FakeRedis()
    try:
        yield Cache(client, default_ttl=3600)
    finally:
        await client.aclose()


async def test_get_returns_none_for_missing(cache: Cache):
    assert await cache.get("missing") is None


async def test_set_and_get_roundtrip(cache: Cache):
    await cache.set("k", {"hello": "world"})
    assert await cache.get("k") == {"hello": "world"}


async def test_set_with_ttl_honored(cache: Cache):
    await cache.set("k", {"a": 1}, ttl=60)
    assert 0 < await cache.ttl("k") <= 60


async def test_convert_key_format():
    k1 = Cache.convert_key("spotify", "track", "abc")
    k2 = Cache.convert_key("spotify", "track", "abc")
    assert k1 == k2
    assert k1 == "cache:spotify:track:abc"


async def test_ping_returns_true(cache: Cache):
    assert await cache.ping() is True
