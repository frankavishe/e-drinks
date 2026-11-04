from dataclasses import fields

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Setting
from app.services.pricing import PricingSettings


async def load_pricing_settings(session: AsyncSession) -> PricingSettings:
    """Read the pricing settings as ints; a missing or blank key keeps its default."""
    keys = [f.name for f in fields(PricingSettings)]
    rows = await session.execute(select(Setting.key, Setting.value).where(Setting.key.in_(keys)))
    return PricingSettings(**{key: int(value) for key, value in rows if value.strip()})
