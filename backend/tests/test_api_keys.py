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


async def test_verify_rejects_oversized_input(session: AsyncSession):
    # Without an upper bound an attacker could POST a multi-MB "key" and force us
    # to run argon2 over all of it; _MAX_KEY_LEN=128 caps that DoS vector cheaply.
    svc = ApiKeyService(session)
    await svc.create(note="x")
    assert await svc.verify("lhk_" + "A" * 200) is None


async def test_verify_runs_argon2_on_unknown_prefix(monkeypatch, session: AsyncSession):
    # Timing-equalisation: a prefix miss must still call argon2.verify (against
    # _DUMMY_HASH) so the attacker cannot distinguish miss from hit by latency.
    from linkhop import api_keys

    real_hasher = api_keys._hasher
    calls = {"n": 0}

    class _CountingHasher:
        def verify(self, hashed: str, presented: str) -> bool:
            calls["n"] += 1
            return real_hasher.verify(hashed, presented)

        def hash(self, s: str) -> str:
            return real_hasher.hash(s)

    monkeypatch.setattr(api_keys, "_hasher", _CountingHasher())

    svc = ApiKeyService(session)
    result = await svc.verify("lhk_no_such_prefix_exists_for_sure")
    assert result is None
    assert calls["n"] == 1  # dummy-hash verify ran despite prefix miss


