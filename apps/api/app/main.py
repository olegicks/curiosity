"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import AppEnv, Settings, get_settings
from app.core.clock import Clock, SystemClock
from app.core.db import create_db_engine, create_session_factory
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import AppVersionGateMiddleware, RequestContextMiddleware
from app.health.router import router as health_router

API_PREFIX = "/v1"


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.app_env != AppEnv.LOCAL)

    engine = create_db_engine(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    openapi_url = f"{API_PREFIX}/openapi.json" if settings.openapi_enabled else None
    app = FastAPI(
        title="Curiosity API",
        version=settings.git_sha,
        openapi_url=openapi_url,
        docs_url=f"{API_PREFIX}/docs" if openapi_url else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.clock = clock or SystemClock()

    register_exception_handlers(app)
    # Starlette runs the last-added middleware first: request context wraps everything.
    app.add_middleware(AppVersionGateMiddleware, min_version=settings.min_app_version_tuple)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    # Domain routers are mounted under API_PREFIX as each module is implemented.
    return app
