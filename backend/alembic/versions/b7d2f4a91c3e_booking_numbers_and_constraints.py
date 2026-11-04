"""booking numbers and constraints

Revision ID: b7d2f4a91c3e
Revises: 9528a00fae20
Create Date: 2026-11-04 19:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7d2f4a91c3e"
down_revision: Union[str, Sequence[str], None] = "9528a00fae20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ["booking_counters"]  # new tables, each gets RLS below
LIVE_REFERENCE = sa.text("reference <> '' AND status <> 'rejected'")


def upgrade() -> None:
    op.create_table(
        "booking_counters",
        sa.Column("year", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("last_no", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("year"),
    )
    # Same rule as the base migration: RLS on, no policies.
    if op.get_context().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')

    op.drop_index("ix_customers_phone", table_name="customers")
    op.create_index("ix_customers_phone", "customers", ["phone"], unique=True)

    op.create_index(
        "uq_payments_booking_reference",
        "payments",
        ["booking_id", "reference"],
        unique=True,
        postgresql_where=LIVE_REFERENCE,
        sqlite_where=LIVE_REFERENCE,
    )


def downgrade() -> None:
    op.drop_index("uq_payments_booking_reference", table_name="payments")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.create_index("ix_customers_phone", "customers", ["phone"], unique=False)
    op.drop_table("booking_counters")
