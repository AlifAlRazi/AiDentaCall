"""Pytest fixtures for DentaCall Agent test suites."""

from collections.abc import AsyncGenerator

import pytest
from dentacall_agent.agent import DentaCallAgent
from dentacall_agent.providers.mock_provider import MockProvider
from dentacall_agent.tools import AgentToolDispatcher
from dentacall_api.main import create_app
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

from data.seed import seed_database


@pytest.fixture(scope="session", autouse=True)
def setup_agent_database() -> None:
    """Ensure database schema is ready before agent tests run."""
    with sync_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist;"))
        Base.metadata.create_all(conn)


@pytest.fixture(autouse=True)
async def seed_data(test_session: AsyncSession) -> None:
    """Seed clinic database with realistic data before each agent test."""
    await seed_database(test_session)


@pytest.fixture
async def test_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated AsyncSession bound with NullPool."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def agent_dispatcher(test_session: AsyncSession) -> AsyncGenerator[AgentToolDispatcher, None]:
    """Provide AgentToolDispatcher hooked into test database via ASGI in-process client."""
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    app.dependency_overrides[get_async_session] = override_get_session

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")

    dispatcher = AgentToolDispatcher(client=client)
    yield dispatcher

    await client.aclose()


@pytest.fixture
def mock_provider() -> MockProvider:
    """Provide a fresh MockProvider for deterministic tests."""
    return MockProvider()


@pytest.fixture
def test_agent(
    mock_provider: MockProvider, agent_dispatcher: AgentToolDispatcher
) -> DentaCallAgent:
    """Provide a configured DentaCallAgent backed by MockProvider and test dispatcher."""
    return DentaCallAgent(provider=mock_provider, dispatcher=agent_dispatcher)
