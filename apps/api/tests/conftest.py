"""Test fixtures and HTTP test client setup for DentaCall API."""

from collections.abc import AsyncGenerator

import pytest
from dentacall_api.main import create_app
from dentacall_api.middleware.idempotency import idempotency_manager
from dentacall_core.db import get_async_session, sync_engine
from dentacall_core.models import Base
from dentacall_core.settings import settings
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session", autouse=True)
def setup_api_database() -> None:
    """Ensure database schema is ready before API tests run."""
    with sync_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist;"))
        Base.metadata.create_all(conn)


@pytest.fixture(autouse=True)
def clear_idempotency_store() -> None:
    """Clear idempotency cache before each test."""
    idempotency_manager.clear()


@pytest.fixture
async def test_session() -> AsyncGenerator[AsyncSession, None]:
    """Isolated database session for API test operations."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with overridden database session dependency."""
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    app.dependency_overrides[get_async_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-API-Key": settings.api_key},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
