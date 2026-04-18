from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from linkhop.models.db import ApiKey, Base, Conversion


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_local = async_sessionmaker(engine, expire_on_commit=False)
    async with session_local() as s:
        yield s
    await engine.dispose()


async def test_conversion_insert_and_fetch(session: AsyncSession):
    c = Conversion(
        short_id="ab3x9k",
        source_url="https://open.spotify.com/track/x",
        source_service="spotify",
        source_type="track",
        source_id="x",
        created_at=datetime.now(tz=UTC),
    )
    session.add(c)
    await session.commit()

    result = await session.scalar(select(Conversion).where(Conversion.short_id == "ab3x9k"))
    assert result is not None
    assert result.source_service == "spotify"
    assert result.access_count == 0


async def test_api_key_insert(session: AsyncSession):
    k = ApiKey(
        id="00000000-0000-0000-0000-000000000001",
        key_prefix="lhk_aaaa",
        key_hash="$argon2id$...",
        note="test",
        created_at=datetime.now(tz=UTC),
    )
    session.add(k)
    await session.commit()

    result = await session.scalar(select(ApiKey).where(ApiKey.key_prefix == "lhk_aaaa"))
    assert result is not None
    assert result.revoked_at is None
