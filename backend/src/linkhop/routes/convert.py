from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from linkhop.cache import Cache
from linkhop.middleware import enforce_rate_limit
from linkhop.models.api import (
    CacheInfo,
    ConvertResponse,
    ShareInfo,
    SourceContent,
    TargetResult,
)
from linkhop.pipeline import Pipeline
from linkhop.short_id import ShortIdService
from linkhop.url_parser import parse

router = APIRouter(prefix="/api/v1", tags=["convert"])


@router.get("/convert", response_model=ConvertResponse)
async def convert(
    request: Request,
    url: str = Query(..., description="Music-service URL"),
    targets: str | None = Query(None, description="Comma-separated list of target service ids"),
    share: bool = Query(False, description="If true, produce a share short-id"),
    _rl=Depends(enforce_rate_limit),
) -> ConvertResponse:
    parsed = parse(url)

    cache: Cache = request.app.state.cache
    cache_key = Cache.convert_key(parsed.service, parsed.type, parsed.id)
    cached = await cache.get(cache_key)

    adapters = request.app.state.adapters

    if cached is not None:
        source_dict = cached["source"]
        targets_dict = {k: TargetResult(**v) for k, v in cached["targets"].items()}
        source_model = SourceContent(**source_dict)
        # Redis TTL returns -2 when the key just expired between get and ttl
        # (and -1 when no TTL is set). Neither is a meaningful number to leak
        # to API clients, so clamp to 0.
        cache_info = CacheInfo(hit=True, ttl_seconds=max(0, await cache.ttl(cache_key)))
    else:
        pipeline = Pipeline(adapters)
        outcome = await pipeline.convert(parsed)

        source_model = SourceContent(
            service=outcome.source.service,
            type=outcome.source.type.value,
            id=outcome.source.id,
            url=outcome.source.url,
            title=outcome.source.title,
            artists=list(outcome.source.artists),
            album=outcome.source.album,
            duration_ms=outcome.source.duration_ms,
            isrc=outcome.source.isrc,
            upc=outcome.source.upc,
            artwork=outcome.source.artwork,
        )
        targets_dict = {
            sid: TargetResult(
                status=t.status, url=t.url, confidence=t.confidence,
                match=t.match, message=t.message,
            )
            for sid, t in outcome.targets.items()
        }
        payload = {
            "source": source_model.model_dump(mode="json"),
            "targets": {k: v.model_dump(mode="json") for k, v in targets_dict.items()},
        }
        await cache.set(cache_key, payload)
        cache_info = CacheInfo(hit=False, ttl_seconds=request.app.state.settings.cache_ttl_seconds)

    if targets:
        wanted = {t.strip() for t in targets.split(",") if t.strip()}
        targets_dict = {k: v for k, v in targets_dict.items() if k in wanted}

    share_info: ShareInfo | None = None
    if share:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            svc = ShortIdService(session)
            sid = await svc.get_or_create(
                source_service=parsed.service,
                source_type=parsed.type,
                source_id=parsed.id,
                source_url=url,
            )
        host = request.headers.get("host", "")
        scheme = request.url.scheme
        share_info = ShareInfo(id=sid, url=f"{scheme}://{host}/api/v1/c/{sid}")

    return ConvertResponse(
        source=source_model,
        targets=targets_dict,
        cache=cache_info,
        share=share_info,
    )
