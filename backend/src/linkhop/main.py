from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI

from linkhop.cache import Cache
from linkhop.config import Settings
from linkhop.db import make_engine, make_session_factory
from linkhop.deps import build_adapter_map
from linkhop.errors import install_error_handlers
from linkhop.ratelimit import RateLimiter
from linkhop.routes import convert as convert_route
from linkhop.routes import health as health_route
from linkhop.routes import services as services_route
from linkhop.routes import share as share_route


@asynccontextmanager
async def lifespan(app: FastAPI):
    # AsyncExitStack so that a failure mid-setup (e.g. make_engine raising on
    # a misconfigured DATABASE_URL) still closes resources allocated earlier in
    # the sequence. Plain try/finally wouldn't cover the setup phase itself.
    settings: Settings = app.state.settings
    async with AsyncExitStack() as stack:
        http = httpx.AsyncClient(timeout=15)
        stack.push_async_callback(http.aclose)
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        stack.push_async_callback(redis_client.aclose)
        engine = make_engine(settings)
        stack.push_async_callback(engine.dispose)
        session_factory = make_session_factory(engine)

        app.state.http = http
        app.state.redis = redis_client
        app.state.cache = Cache(redis_client, default_ttl=settings.cache_ttl_seconds)
        app.state.ratelimiter = RateLimiter(
            redis_client,
            anonymous_per_minute=settings.rate_anonymous_per_minute,
            with_key_per_minute=settings.rate_with_key_per_minute,
        )
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.adapters = build_adapter_map(settings, http)

        yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="linkhop", version="0.1.0",
        docs_url="/api/docs", openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    install_error_handlers(app)
    app.include_router(health_route.router)
    app.include_router(services_route.router)
    app.include_router(convert_route.router)
    app.include_router(share_route.router)
    return app


app = create_app()
