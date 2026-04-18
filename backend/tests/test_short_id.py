import re

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from linkhop.models.db import Base
from linkhop.short_id import ShortIdService, generate_short_id


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_local = async_sessionmaker(engine, expire_on_commit=False)
        async with session_local() as s:
            yield s
    finally:
        await engine.dispose()


def test_generate_short_id_format():
    sid = generate_short_id()
    assert re.match(r"^[A-Za-z0-9]{6}$", sid)


def test_generate_short_id_unique():
    ids = {generate_short_id() for _ in range(1000)}
    assert len(ids) == 1000


async def test_service_returns_existing_for_same_source(session: AsyncSession):
    svc = ShortIdService(session)
    sid1 = await svc.get_or_create(
        source_service="spotify", source_type="track", source_id="x",
        source_url="https://open.spotify.com/track/x",
    )
    sid2 = await svc.get_or_create(
        source_service="spotify", source_type="track", source_id="x",
        source_url="https://open.spotify.com/track/x",
    )
    assert sid1 == sid2


async def test_service_creates_different_for_different_source(session: AsyncSession):
    svc = ShortIdService(session)
    a = await svc.get_or_create(
        source_service="spotify", source_type="track", source_id="x",
        source_url="https://open.spotify.com/track/x",
    )
    b = await svc.get_or_create(
        source_service="deezer", source_type="track", source_id="x",
        source_url="https://www.deezer.com/track/x",
    )
    assert a != b


async def test_service_lookup_by_short_id(session: AsyncSession):
    svc = ShortIdService(session)
    sid = await svc.get_or_create(
        source_service="spotify", source_type="track", source_id="x",
        source_url="https://open.spotify.com/track/x",
    )
    row = await svc.lookup(sid)
    assert row is not None
    assert row.source_service == "spotify"
    assert row.source_id == "x"
    assert row.access_count == 1  # lookup bumped counter


async def test_service_returns_existing_short_id_on_source_race():
    # Two concurrent sessions call get_or_create with the same source. Session A's
    # SELECT happens before B commits, so A sees no existing row and attempts INSERT —
    # that INSERT must hit uq_conversion_source and the service must load B's short_id
    # rather than burning retries generating fresh ids that would all fail the same way.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_local = async_sessionmaker(engine, expire_on_commit=False)

        async with session_local() as session_a, session_local() as session_b:
            svc_a = ShortIdService(session_a)
            svc_b = ShortIdService(session_b)

            # Pre-fetch both "no existing" lookups before either commits.
            existing_a = await svc_a._find_existing("spotify", "track", "race")
            existing_b = await svc_b._find_existing("spotify", "track", "race")
            assert existing_a is None and existing_b is None

            # B wins the race and commits first.
            sid_b = await svc_b.get_or_create(
                source_service="spotify", source_type="track", source_id="race",
                source_url="https://open.spotify.com/track/race",
            )
            # A now runs its insert; the IntegrityError path must resolve to sid_b.
            sid_a = await svc_a.get_or_create(
                source_service="spotify", source_type="track", source_id="race",
                source_url="https://open.spotify.com/track/race",
            )
            assert sid_a == sid_b
    finally:
        await engine.dispose()
