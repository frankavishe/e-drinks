from app.models import Setting
from app.services.pricing import PricingSettings
from app.services.settings_store import (
    PUBLIC_KEYS,
    load_notification_email,
    load_pricing_settings,
    load_public_settings,
)


async def test_public_settings_are_whitelisted(seeded_session):
    seeded_session.add(Setting(key="internal_secret", value="x"))
    await seeded_session.commit()
    public = await load_public_settings(seeded_session)
    assert set(public) == set(PUBLIC_KEYS)
    assert public["whatsapp_number"] == "255700000000"
    assert public["business_name"] == "e-drinks"
    assert "notification_email" not in public
    assert "min_order" not in public


async def test_public_settings_missing_keys_are_blank(session):
    public = await load_public_settings(session)
    assert public["mpesa_till"] == ""


async def test_notification_email_prefers_the_setting(seeded_session, monkeypatch):
    monkeypatch.setattr("app.services.settings_store.get_settings", lambda: _Env("env@example.com"))
    assert await load_notification_email(seeded_session) == "env@example.com"
    setting = await seeded_session.get(Setting, "notification_email")
    setting.value = "owner@example.com"
    await seeded_session.commit()
    assert await load_notification_email(seeded_session) == "owner@example.com"


class _Env:
    def __init__(self, admin_email):
        self.admin_email = admin_email


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
