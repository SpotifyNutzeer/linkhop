from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from linkhop.models.api import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> JSONResponse:
    redis_ok = await request.app.state.cache.ping()
    pg_ok = False
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        pg_ok = True
    except Exception:
        pg_ok = False

    status = "ok" if (redis_ok and pg_ok) else "degraded"
    code = 200 if status == "ok" else 503
    body = HealthResponse(status=status, redis=redis_ok, postgres=pg_ok).model_dump()
    return JSONResponse(status_code=code, content=body)
