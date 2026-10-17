import asyncio
import os
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.team import Team, TeamMembership
from app.models.enums import TeamRole
from app.services.auth_service import get_password_hash, create_access_token

# Use a distinct test database
TEST_DB_URL = "sqlite+aiosqlite:///./test_newtonite_ops.db"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True, scope="function")
async def setup_test_db():
    """Initializes tables before each test and drops them afterwards for clean test isolation."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    if os.path.exists("./test_newtonite_ops.db"):
        try:
            os.remove("./test_newtonite_ops.db")
        except Exception:
            pass


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def seed_test_data(db_session: AsyncSession):
    """Seeds baseline teams and users with defined roles for test cases."""
    pwd = get_password_hash("password123")

    # Team: Platform Engineering
    team = Team(name="Platform Engineering", description="Core Platform Infrastructure")
    db_session.add(team)
    await db_session.flush()

    # Users
    alice = User(name="Alice Morgan", email="alice@test.io", hashed_password=pwd)
    bob = User(name="Bob Chen", email="bob@test.io", hashed_password=pwd)
    charlie = User(name="Charlie Davis", email="charlie@test.io", hashed_password=pwd)
    owen = User(name="Outsider Owen", email="owen@external.io", hashed_password=pwd)

    db_session.add_all([alice, bob, charlie, owen])
    await db_session.flush()

    # Memberships: Alice is Lead, Bob is Member, Charlie is Viewer. Owen has no membership.
    db_session.add(TeamMembership(user_id=alice.id, team_id=team.id, role=TeamRole.LEAD))
    db_session.add(TeamMembership(user_id=bob.id, team_id=team.id, role=TeamRole.MEMBER))
    db_session.add(TeamMembership(user_id=charlie.id, team_id=team.id, role=TeamRole.VIEWER))

    await db_session.commit()
    return {
        "team": team,
        "alice": alice,
        "bob": bob,
        "charlie": charlie,
        "owen": owen,
    }


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    def _make_headers(user_id: int, email: str, name: str):
        token = create_access_token({"sub": str(user_id), "email": email, "name": name})
        return {"Authorization": f"Bearer {token}"}
    return _make_headers
