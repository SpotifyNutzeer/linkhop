from __future__ import annotations

from fastapi import Header, Request

from linkhop.api_keys import ApiKeyService
from linkhop.errors import AppError


async def enforce_rate_limit(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    limiter = request.app.state.ratelimiter

    key_record = None
    if x_api_key:
        async with request.app.state.session_factory() as session:
            key_record = await ApiKeyService(session).verify(x_api_key)

    if x_api_key and key_record is None:
        raise AppError(code="invalid_api_key", status=401, message="API key not valid")

    if key_record:
        identifier = f"key:{key_record.id}"
        ok = await limiter.check(
            identifier=identifier, is_authenticated=True,
            override=key_record.rate_limit_override,
        )
    else:
        client_host = request.client.host if request.client else "unknown"
        identifier = f"ip:{client_host}"
        ok = await limiter.check(identifier=identifier, is_authenticated=False)

    if not ok:
        raise AppError(code="rate_limited", status=429, message="rate limit exceeded")

    return {"api_key_id": key_record.id if key_record else None}
