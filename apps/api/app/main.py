"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.ai.provider import ExplanationProvider, build_provider
from app.ai.router import router as ai_router
from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.config import AppEnv, Settings, get_settings
from app.content.router import router as content_router
from app.core.clock import Clock, SystemClock
from app.core.db import create_db_engine, create_session_factory
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import AppVersionGateMiddleware, RequestContextMiddleware
from app.core.ratelimit import DisabledRateLimiter, FixedWindowRateLimiter, RateLimiter
from app.gamification.router import router as gamification_router
from app.health.router import router as health_router
from app.learning.router import router as learning_router
from app.reviews.router import router as reviews_router
from app.users.router import router as users_router

API_PREFIX = "/v1"


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    ai_provider: ExplanationProvider | None = None,
) -> FastAPI:
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
    rate_limiter: RateLimiter = (
        FixedWindowRateLimiter() if settings.rate_limit_enabled else DisabledRateLimiter()
    )
    app.state.rate_limiter = rate_limiter
    app.state.ai_provider = ai_provider or build_provider(settings)

    register_exception_handlers(app)
    # Starlette runs the last-added middleware first: request context wraps everything.
    app.add_middleware(AppVersionGateMiddleware, min_version=settings.min_app_version_tuple)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(users_router, prefix=API_PREFIX)
    app.include_router(content_router, prefix=API_PREFIX)
    app.include_router(learning_router, prefix=API_PREFIX)
    app.include_router(reviews_router, prefix=API_PREFIX)
    app.include_router(gamification_router, prefix=API_PREFIX)
    app.include_router(ai_router, prefix=API_PREFIX)
    app.include_router(analytics_router, prefix=API_PREFIX)
    # Lesson illustrations from content/media (validated at import; read-only).
    app.mount(
        "/media", StaticFiles(directory=settings.content_dir / "media", check_dir=False), "media"
    )
    return app
