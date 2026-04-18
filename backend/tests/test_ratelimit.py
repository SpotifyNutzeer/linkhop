import fakeredis.aioredis
import pytest

from linkhop.ratelimit import RateLimiter


@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.aclose()


async def test_allows_under_limit(redis_client):
    rl = RateLimiter(redis_client, anonymous_per_minute=3, with_key_per_minute=100)
    for _ in range(3):
        assert await rl.check(identifier="1.2.3.4", is_authenticated=False) is True


async def test_blocks_over_limit(redis_client):
    rl = RateLimiter(redis_client, anonymous_per_minute=3, with_key_per_minute=100)
    for _ in range(3):
        await rl.check(identifier="1.2.3.4", is_authenticated=False)
    assert await rl.check(identifier="1.2.3.4", is_authenticated=False) is False


async def test_separate_counters_per_identifier(redis_client):
    rl = RateLimiter(redis_client, anonymous_per_minute=2, with_key_per_minute=100)
    for _ in range(2):
        await rl.check(identifier="a", is_authenticated=False)
    assert await rl.check(identifier="b", is_authenticated=False) is True


async def test_authenticated_uses_higher_limit(redis_client):
    rl = RateLimiter(redis_client, anonymous_per_minute=2, with_key_per_minute=5)
    for _ in range(5):
        assert await rl.check(identifier="key:xyz", is_authenticated=True) is True
    assert await rl.check(identifier="key:xyz", is_authenticated=True) is False


async def test_custom_override_used_when_provided(redis_client):
    rl = RateLimiter(redis_client, anonymous_per_minute=2, with_key_per_minute=5)
    for _ in range(9):
        assert await rl.check(identifier="key:k", is_authenticated=True, override=9) is True
    assert await rl.check(identifier="key:k", is_authenticated=True, override=9) is False
