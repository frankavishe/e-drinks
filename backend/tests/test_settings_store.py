from app.models import Setting
from app.services.pricing import PricingSettings
from app.services.settings_store import load_pricing_settings


async def test_reads_seeded_settings_as_ints(seeded_session):
    assert await load_pricing_settings(seeded_session) == PricingSettings(
        min_order=300000,
        notice_days=3,
        notice_days_servers=7,
        deposit_percent=50,
        balance_due_days=3,
    )


async def test_missing_keys_use_defaults(session):
    assert await load_pricing_settings(session) == PricingSettings()


async def test_blank_value_uses_default(seeded_session):
    setting = await seeded_session.get(Setting, "notice_days")
    setting.value = "  "
    await seeded_session.commit()
    assert (await load_pricing_settings(seeded_session)).notice_days == PricingSettings().notice_days


async def test_edited_value_is_used(seeded_session):
    setting = await seeded_session.get(Setting, "min_order")
    setting.value = "450000"
    await seeded_session.commit()
    assert (await load_pricing_settings(seeded_session)).min_order == 450000
