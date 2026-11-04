from dataclasses import fields

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Setting
from app.services.pricing import PricingSettings

# The only settings the public API may return. Anything else stays server-side.
PUBLIC_KEYS = (
    "business_name",
    "whatsapp_number",
    "policy_text_sw",
    "policy_text_en",
    "mpesa_till",
    "tigopesa_lipa",
    "airtel_lipa",
    "bank_details",
)


async def load_pricing_settings(session: AsyncSession) -> PricingSettings:
    """Read the pricing settings as ints; a missing or blank key keeps its default."""
    keys = [f.name for f in fields(PricingSettings)]
    rows = await session.execute(select(Setting.key, Setting.value).where(Setting.key.in_(keys)))
    return PricingSettings(**{key: int(value) for key, value in rows if value.strip()})


async def load_public_settings(session: AsyncSession) -> dict[str, str]:
    """Whitelisted settings as strings; a missing key reads as blank."""
    rows = await session.execute(
        select(Setting.key, Setting.value).where(Setting.key.in_(PUBLIC_KEYS))
    )
    return {**dict.fromkeys(PUBLIC_KEYS, ""), **{key: value for key, value in rows}}


async def load_notification_email(session: AsyncSession) -> str:
    """Where business emails go: the setting, or ADMIN_EMAIL until the owner sets one."""
    value = await session.scalar(select(Setting.value).where(Setting.key == "notification_email"))
    return (value or "").strip() or get_settings().admin_email
