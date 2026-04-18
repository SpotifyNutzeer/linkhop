import asyncio
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from linkhop.api_keys import ApiKeyService
from linkhop.cache import Cache
from linkhop.config import Settings
from linkhop.main import create_app
from linkhop.models.db import Base
from linkhop.models.domain import ContentType, ResolvedContent
from linkhop.ratelimit import RateLimiter


class StubAdapter:
    service_id = "tidal"
    capabilities = SimpleNamespace(track=True, album=True, artist=True)
    async def resolve(self, parsed):
        return ResolvedContent(
            service="tidal", type=ContentType.TRACK, id="1",
            url="https://tidal.com/track/1", title="N", artists=("K",),
            album="A", duration_ms=100000, isrc=None, upc=None, artwork="",
        )
    async def search(self, meta, t):
        return []


@pytest.fixture
def app_with_limits():
    settings = Settings()
    settings.rate_anonymous_per_minute = 2
    settings.rate_with_key_per_minute = 10
    app = create_app(settings)

    async def _startup():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        app.state.engine = engine
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        rc = fakeredis.aioredis.FakeRedis()
        app.state.redis = rc
        app.state.cache = Cache(rc, default_ttl=60)
        # Aus settings lesen, damit das Setup single-sourced bleibt — sonst
        # driften Fixture-Konstante und Settings-Mutation lautlos auseinander.
        app.state.ratelimiter = RateLimiter(
            rc,
            anonymous_per_minute=settings.rate_anonymous_per_minute,
            with_key_per_minute=settings.rate_with_key_per_minute,
        )
        app.state.adapters = {"tidal": StubAdapter()}

    asyncio.run(_startup())
    return app


def test_anonymous_rate_limited(app_with_limits):
    # Wie in Task 20/21: KEIN `with`-Block, sonst triggert FastAPI den echten
    # Lifespan, der app.state.ratelimiter/cache/session_factory/adapters
    # überschreibt und die Fixture-Stubs wegwirft.
    client = TestClient(app_with_limits)
    for _ in range(2):
        assert client.get("/api/v1/convert", params={"url": "https://tidal.com/track/1"}).status_code == 200
    resp = client.get("/api/v1/convert", params={"url": "https://tidal.com/track/1"})
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limited"


def test_valid_key_uses_higher_limit(app_with_limits):
    async def _create_key():
        async with app_with_limits.state.session_factory() as s:
            plain, _ = await ApiKeyService(s).create(note="test")
            return plain
    plain = asyncio.run(_create_key())

    # Auch hier: KEIN `with`-Block — sonst überschreibt der reale Lifespan
    # die in _startup() gebaute Engine, und der eben erzeugte API-Key wäre
    # aus Sicht des HTTP-Requests nicht mehr in der DB.
    client = TestClient(app_with_limits)
    for _ in range(5):
        r = client.get(
            "/api/v1/convert",
            params={"url": "https://tidal.com/track/1"},
            headers={"X-API-Key": plain},
        )
        assert r.status_code == 200
