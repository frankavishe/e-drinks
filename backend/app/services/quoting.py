"""Load everything a quote needs and price it. /public/quote and booking creation both use this."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.availability import addon_availability, is_rush, today_eat
from app.services.catalog_loader import load_catalog
from app.services.pricing import Quote, QuoteRequest, build_quote, has_staff_addon
from app.services.settings_store import load_pricing_settings


async def compute_quote(session: AsyncSession, req: QuoteRequest) -> Quote:
    """Raises QuoteError or CatalogError when the request can't be priced."""
    catalog = await load_catalog(session)
    settings = await load_pricing_settings(session)
    availability = await addon_availability(
        session, [addon_id for addon_id, _ in req.addons], req.setup_at, req.collect_at
    )
    rush = is_rush(req.event_date, today_eat(), has_staff_addon(req, catalog), settings)
    return build_quote(req, catalog, settings, availability=availability, is_rush=rush)
