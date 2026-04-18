import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from linkhop.api_keys import KEY_PREFIX_LEN, ApiKeyService
from linkhop.models.db import Base


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


async def test_create_returns_key_with_prefix(session: AsyncSession):
    svc = ApiKeyService(session)
    plain, record = await svc.create(note="paul")
    assert plain.startswith("lhk_")
    assert len(record.key_prefix) == KEY_PREFIX_LEN
    assert plain.startswith(record.key_prefix)


async def test_verify_correct_key(session: AsyncSession):
    svc = ApiKeyService(session)
    plain, _ = await svc.create(note="x")
    verified = await svc.verify(plain)
    assert verified is not None


async def test_verify_wrong_key(session: AsyncSession):
    svc = ApiKeyService(session)
    await svc.create(note="x")
    assert await svc.verify("lhk_wrong0000notvalid") is None


async def test_revoked_key_does_not_verify(session: AsyncSession):
    svc = ApiKeyService(session)
    plain, record = await svc.create(note="x")
    await svc.revoke(record.id)
    assert await svc.verify(plain) is None


async def test_list_and_revoke(session: AsyncSession):
    svc = ApiKeyService(session)
    _, a = await svc.create(note="a")
    _, b = await svc.create(note="b")
    await svc.revoke(a.id)
    keys = await svc.list_all()
    active = [k for k in keys if k.revoked_at is None]
    assert len(active) == 1
    assert active[0].id == b.id


