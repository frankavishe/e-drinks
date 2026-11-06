import uuid

from sqlalchemy import func, select

from app.models import Addon, Area, Package, PriceTier, Product, Profile, Setting, Zone
from app.seed import seed


async def count(session, model):
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_seed_creates_catalog(session):
    await seed(session)
    assert await count(session, Product) >= 12
    assert await count(session, PriceTier) >= 24
    assert await count(session, Package) == 4
    assert await count(session, Addon) == 4
    assert await count(session, Zone) >= 3
    masaki = (await session.execute(select(Area).where(Area.name == "Masaki"))).scalar_one()
    assert masaki.zone_id is not None
    name = await session.get(Setting, "business_name")
    assert name.value == "e-drinks"
    assert (await session.get(Setting, "min_order")).value == "300000"


async def test_seed_is_idempotent(session):
    await seed(session)
    before = {m: await count(session, m) for m in (Product, PriceTier, Package, Addon, Zone, Area, Setting)}
    await seed(session)
    after = {m: await count(session, m) for m in before}
    assert before == after


async def test_seed_creates_owner_profile_when_given(session):
    uid = uuid.uuid4()
    await seed(session, owner_id=uid, owner_email="owner@example.com")
    await seed(session, owner_id=uid, owner_email="owner@example.com")
    owner = await session.get(Profile, uid)
    assert owner.role == "owner"
    assert await count(session, Profile) == 1


async def test_seed_creates_staff_profile_when_given(session):
    uid = uuid.uuid4()
    await seed(session, staff_id=uid, staff_email="staff@example.com")
    await seed(session, staff_id=uid, staff_email="staff@example.com")
    staff = await session.get(Profile, uid)
    assert staff.role == "staff"
    assert staff.email == "staff@example.com"
    assert await count(session, Profile) == 1


async def test_seed_does_not_demote_an_existing_owner_to_staff(session):
    uid = uuid.uuid4()
    await seed(session, owner_id=uid, owner_email="both@example.com")
    await seed(session, staff_id=uid, staff_email="both@example.com")
    assert (await session.get(Profile, uid)).role == "owner"
