from __future__ import annotations

from fastapi import APIRouter, Request

from linkhop.errors import AppError
from linkhop.models.api import ConvertResponse
from linkhop.routes.convert import convert as convert_view
from linkhop.short_id import ShortIdService

router = APIRouter(prefix="/api/v1", tags=["share"])


@router.get("/c/{short_id}", response_model=ConvertResponse)
async def open_share(short_id: str, request: Request):
    async with request.app.state.session_factory() as session:
        svc = ShortIdService(session)
        row = await svc.lookup(short_id)
        if row is None:
            raise AppError(code="share_not_found", status=404, message=f"short id not found: {short_id}")
        source_url = row.source_url
    return await convert_view(request, url=source_url, targets=None, share=False)
