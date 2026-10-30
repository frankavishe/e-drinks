import time
import uuid

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI

from app.auth import get_current_profile, require_role
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Profile

SECRET = "test-secret-at-least-32-bytes-long!!"


def make_token(sub: uuid.UUID, exp_offset: int = 3600, secret: str = SECRET) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": str(sub), "aud": "authenticated", "role": "authenticated",
         "iat": now, "exp": now + exp_offset},
        secret,
        algorithm="HS256",
    )


@pytest.fixture
def api(session):
    app = FastAPI()

    @app.get("/me")
    async def me(profile: Profile = Depends(get_current_profile)):
        return {"role": profile.role}

    @app.get("/owner-only")
    async def owner_only(profile: Profile = Depends(require_role("owner"))):
        return {"ok": True}

    async def _session():
        yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_settings] = lambda: Settings(supabase_jwt_secret=SECRET)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def add_profile(session, role: str) -> uuid.UUID:
    uid = uuid.uuid4()
    session.add(Profile(id=uid, role=role, name="X"))
    await session.commit()
    return uid


async def test_valid_token_returns_profile(api, session):
    uid = await add_profile(session, "staff")
    res = await api.get("/me", headers={"Authorization": f"Bearer {make_token(uid)}"})
    assert res.status_code == 200
    assert res.json() == {"role": "staff"}


async def test_missing_token_is_401(api):
    assert (await api.get("/me")).status_code == 401


async def test_expired_token_is_401(api, session):
    uid = await add_profile(session, "owner")
    res = await api.get("/me", headers={"Authorization": f"Bearer {make_token(uid, -10)}"})
    assert res.status_code == 401


async def test_bad_signature_is_401(api, session):
    uid = await add_profile(session, "owner")
    bad = make_token(uid, secret="another-secret-that-is-32-bytes-long")
    assert (await api.get("/me", headers={"Authorization": f"Bearer {bad}"})).status_code == 401


async def test_token_without_profile_is_403(api):
    res = await api.get("/me", headers={"Authorization": f"Bearer {make_token(uuid.uuid4())}"})
    assert res.status_code == 403


async def test_wrong_role_is_403(api, session):
    uid = await add_profile(session, "staff")
    res = await api.get("/owner-only", headers={"Authorization": f"Bearer {make_token(uid)}"})
    assert res.status_code == 403


async def test_right_role_passes(api, session):
    uid = await add_profile(session, "owner")
    res = await api.get("/owner-only", headers={"Authorization": f"Bearer {make_token(uid)}"})
    assert res.status_code == 200
