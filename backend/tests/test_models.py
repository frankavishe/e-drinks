from sqlalchemy import create_engine, inspect

from app.db import Base
import app.models  # noqa: F401  (registers tables)

EXPECTED = {
    "settings", "profiles", "customers", "products", "price_tiers", "packages", "package_rules",
    "addons", "zones", "areas", "venues", "bookings", "booking_items", "booking_addons",
    "booking_status_history", "payments", "stock_levels", "stock_movements", "purchase_needs",
    "commissions", "gallery_images",
}


def test_all_spec_tables_create():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    assert EXPECTED <= set(inspect(engine).get_table_names())


def test_rls_migration_covers_every_table():
    import importlib.util
    from pathlib import Path

    path = next(Path(__file__).parent.parent.glob("alembic/versions/*_base_schema.py"))
    spec = importlib.util.spec_from_file_location("base_schema", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert set(mod.TABLES) == set(Base.metadata.tables)
