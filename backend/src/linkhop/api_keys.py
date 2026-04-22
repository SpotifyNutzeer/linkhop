from __future__ import annotations

import contextlib
import secrets
import string
import uuid
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from linkhop.models.db import ApiKey

# Prefix = "lhk_" + 8 random chars; 62^8 ≈ 2.2e14 combinations, so a prefix collision
# with the unique key_prefix DB constraint is astronomically unlikely at this scale.
# (Before raising the length, 62^4 ≈ 14.7 M gave a birthday-paradox ~30% collision
# at just 10k active keys, unhandled by create().)
KEY_PREFIX_LEN = 12
_KEY_SUFFIX_LEN = 32
# Upper bound on what we'll feed into argon2.verify; the real keys are 36 chars.
# Without a cap an attacker could POST a 10 MB "key" and force us to hash it.
_MAX_KEY_LEN = 128
_ALPHA = string.ascii_letters + string.digits
_hasher = PasswordHasher()
# Dummy hash used in verify() to equalise wall-clock between prefix-miss and
# prefix-hit so timing alone cannot confirm whether a given prefix is live.
_DUMMY_HASH = _hasher.hash("dummy")


def _generate_plain_key() -> tuple[str, str]:
    """Returns (full_key, prefix)."""
    body = "".join(secrets.choice(_ALPHA) for _ in range(_KEY_SUFFIX_LEN))
    full = f"lhk_{body}"
    prefix = full[:KEY_PREFIX_LEN]
    return full, prefix


class ApiKeyService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, *, note: str | None = None,
                     rate_limit_override: int | None = None) -> tuple[str, ApiKey]:
        full, prefix = _generate_plain_key()
        row = ApiKey(
            id=str(uuid.uuid4()),
            key_prefix=prefix,
            key_hash=_hasher.hash(full),
            note=note,
            rate_limit_override=rate_limit_override,
        )  # created_at comes from ApiKey.server_default=func.now()
        self._s.add(row)
        await self._s.commit()
        await self._s.refresh(row)
        return full, row

    async def verify(self, presented: str) -> ApiKey | None:
        if not (KEY_PREFIX_LEN <= len(presented) <= _MAX_KEY_LEN):
            return None
        prefix = presented[:KEY_PREFIX_LEN]
        row = await self._s.scalar(
            select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.revoked_at.is_(None))
        )
        if row is None:
            # Run argon2 against a dummy hash anyway so miss and hit take the same
            # wall-clock time — otherwise timing alone confirms which prefixes are live.
            with contextlib.suppress(VerifyMismatchError):
                _hasher.verify(_DUMMY_HASH, presented)
            return None
        try:
            _hasher.verify(row.key_hash, presented)
        except VerifyMismatchError:
            return None
        return row

    async def revoke(self, key_id: str) -> int:
        # Rückgabe = matched rows, damit Aufrufer (CLI) zwischen "revoked" und
        # "kein Treffer" unterscheiden kann. Ein blindes UPDATE auf eine
        # falsche UUID gibt sonst lautlos Erfolg — klassische Ops-Falle.
        result = await self._s.execute(
            update(ApiKey).where(ApiKey.id == key_id).values(revoked_at=datetime.now(tz=UTC))
        )
        await self._s.commit()
        # execute() ist statisch Result[Any], zur Laufzeit für DML aber
        # CursorResult — rowcount existiert, mypy kann es nicht verifizieren.
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def list_all(self) -> list[ApiKey]:
        result = await self._s.scalars(select(ApiKey).order_by(ApiKey.created_at))
        return list(result.all())
