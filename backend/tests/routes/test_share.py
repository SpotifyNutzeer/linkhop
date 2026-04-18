# Verwendet den gleichen `patched_app`-Fixture-Pattern wie test_convert.py.
# Für Kürze: Test prüft dass lookup 404 liefert wenn short_id fehlt, und 200 wenn vorhanden.

import asyncio
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from linkhop.cache import Cache
from linkhop.config import Settings
from linkhop.main import create_app
from linkhop.models.db import Base
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.ratelimit import RateLimiter


class StubAdapter:
    def __init__(self, sid: str, resolve_value=None, search_value=None):
        self.service_id = sid
        self.capabilities = SimpleNamespace(track=True, album=True, artist=True, supports=lambda t: True)
        self._r = resolve_value
        self._s = search_value or []

    async def resolve(self, parsed): return self._r
    async def search(self, meta, t): return self._s


@pytest.fixture
def app_with_share():
    app = create_app(Settings())

    async def _startup():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        app.state.engine = engine
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)

        rc = fakeredis.aioredis.FakeRedis()
        app.state.redis = rc
        app.state.cache = Cache(rc, default_ttl=60)
        app.state.ratelimiter = RateLimiter(
            rc, anonymous_per_minute=1000, with_key_per_minute=1000,
        )
        app.state.adapters = {
            "tidal": StubAdapter("tidal", resolve_value=ResolvedContent(
                service="tidal", type=ContentType.TRACK, id="1",
                url="https://tidal.com/track/1", title="N", artists=("K",),
                album="Outrun", duration_ms=200000, isrc=None, upc=None, artwork="",
            )),
            "spotify": StubAdapter("spotify", search_value=[
                SearchHit(service="spotify", id="sp1",
                          url="https://open.spotify.com/track/sp1",
                          confidence=1.0, match="isrc"),
            ]),
        }

    asyncio.run(_startup())
    return app


def test_share_404_for_unknown(app_with_share):
    # Wie in Task 20: KEIN `with`-Block, sonst triggert FastAPI den echten
    # Lifespan, der app.state.cache/adapters/session_factory überschreibt.
    client = TestClient(app_with_share)
    resp = client.get("/api/v1/c/notthere")
    assert resp.status_code == 404


def test_share_200_after_create(app_with_share):
    client = TestClient(app_with_share)
    create_resp = client.get(
        "/api/v1/convert",
        params={"url": "https://tidal.com/track/1", "share": "true"},
    )
    sid = create_resp.json()["share"]["id"]
    get_resp = client.get(f"/api/v1/c/{sid}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["source"]["title"] == "N"
    # Share-Lookup ruft convert_view mit share=False; die Antwort darf also
    # keinen verschachtelten Share-Block mehr enthalten.
    assert body["share"] is None
