import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dentacall_core.db import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dentacall_api.errors import register_exception_handlers
from dentacall_api.middleware.logging_middleware import CallIDLoggingMiddleware
from dentacall_api.middleware.rate_limiter import RateLimitMiddleware
from dentacall_api.routers import dashboard, livekit, metrics, telephony, tools

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context for startup and shutdown hooks."""
    try:
        await init_db()
    except Exception as e:
        logger.warning(f"Database initialization deferred or unavailable: {e}")
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="DentaCall Tool API",
        description="Production-grade AI receptionist tool API for dental practice management.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom Middleware
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CallIDLoggingMiddleware)

    # Custom Exception Handlers
    register_exception_handlers(app)

    # Include Routers
    app.include_router(tools.router)
    app.include_router(livekit.router)
    app.include_router(telephony.router, prefix="/api")
    app.include_router(metrics.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")

    @app.get("/health", tags=["Health"], summary="System Health Check")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "dentacall-api", "version": "0.1.0"}

    return app


app = create_app()
