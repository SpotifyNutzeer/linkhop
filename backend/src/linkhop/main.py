from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI

from linkhop.cache import Cache
from linkhop.config import Settings
from linkhop.db import make_engine, make_session_factory
from linkhop.deps import build_adapter_map
from linkhop.errors import install_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    http = httpx.AsyncClient(timeout=15)
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)

    app.state.http = http
    app.state.redis = redis_client
    app.state.cache = Cache(redis_client, default_ttl=settings.cache_ttl_seconds)
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.adapters = build_adapter_map(settings, http)

    try:
        yield
    finally:
        await http.aclose()
        await redis_client.aclose()
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="linkhop", version="0.1.0",
        docs_url="/api/docs", openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    install_error_handlers(app)
    return app


app = create_app()
