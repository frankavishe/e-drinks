import httpx
import pytest
import pytest_asyncio
import resend
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.config import get_settings
from app.db import Base, get_session
from app.main import app as fastapi_app
from app.routers.public import booking_limiter, lookup_limiter
from app.seed import seed


@pytest.fixture(autouse=True)
def reset_rate_limits():
    booking_limiter.clear()
    lookup_limiter.clear()


@pytest.fixture(autouse=True)
def sent_emails(monkeypatch):
    """Records what would be sent. No test can reach Resend, whatever backend/.env holds."""
    sent: list[dict] = []
    monkeypatch.setattr(resend.Emails, "send", lambda params: sent.append(params))
    settings = get_settings()
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "admin_email", "admin@example.test")
    return sent


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_session(session):
    await seed(session)
    return session


@pytest_asyncio.fixture
async def client(seeded_session):
    async def override_session():
        yield seeded_session

    fastapi_app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    fastapi_app.dependency_overrides.pop(get_session, None)
