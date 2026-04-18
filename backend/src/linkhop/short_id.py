from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from linkhop.models.db import Conversion

_ALPHA = string.ascii_letters + string.digits  # 62 chars


def generate_short_id(length: int = 6) -> str:
    return "".join(secrets.choice(_ALPHA) for _ in range(length))


class ShortIdService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_or_create(
        self,
        *,
        source_service: str,
        source_type: str,
        source_id: str,
        source_url: str,
    ) -> str:
        existing_sid = await self._find_existing(source_service, source_type, source_id)
        if existing_sid is not None:
            return existing_sid

        for _ in range(10):
            sid = generate_short_id()
            row = Conversion(
                short_id=sid,
                source_url=source_url,
                source_service=source_service,
                source_type=source_type,
                source_id=source_id,
                created_at=datetime.now(tz=UTC),
            )
            self._s.add(row)
            try:
                await self._s.commit()
                return sid
            except IntegrityError:
                await self._s.rollback()
                # Two distinct unique constraints can fail here:
                #   - PK(short_id)            -> real short-id collision -> retry with a new id
                #   - uq_conversion_source    -> another request inserted the same source
                #                                concurrently -> load its short_id, don't retry
                # Without this check the source-race would burn all 10 retries pointlessly.
                raced_sid = await self._find_existing(source_service, source_type, source_id)
                if raced_sid is not None:
                    return raced_sid
                continue

        raise RuntimeError("failed to allocate short id after 10 retries")

    async def _find_existing(
        self, source_service: str, source_type: str, source_id: str
    ) -> str | None:
        row = await self._s.scalar(
            select(Conversion).where(
                Conversion.source_service == source_service,
                Conversion.source_type == source_type,
                Conversion.source_id == source_id,
            )
        )
        return row.short_id if row is not None else None

    async def lookup(self, short_id: str) -> Conversion | None:
        row = await self._s.scalar(
            select(Conversion).where(Conversion.short_id == short_id)
        )
        if row is None:
            return None
        await self._s.execute(
            update(Conversion)
            .where(Conversion.short_id == short_id)
            .values(
                access_count=Conversion.access_count + 1,
                last_access_at=datetime.now(tz=UTC),
            )
        )
        await self._s.commit()
        await self._s.refresh(row)
        return row
