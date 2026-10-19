"""Shared test fixtures for DentaCall core test suite."""

from collections.abc import AsyncGenerator

import pytest
from dentacall_core.db import sync_engine
from dentacall_core.models import Base
from dentacall_core.settings import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session", autouse=True)
def setup_database_schema() -> None:
    """Ensure database schema is created once synchronously before any tests run."""
    with sync_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist;"))
        Base.metadata.create_all(conn)


@pytest.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated AsyncSession using NullPool to prevent closed event loop issues across tests."""
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        echo=False,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()
