"""booking refund due and internal notes

Revision ID: c4e8a1d27f60
Revises: b7d2f4a91c3e
Create Date: 2026-11-06 09:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8a1d27f60"
down_revision: Union[str, Sequence[str], None] = "b7d2f4a91c3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("refund_due", sa.BigInteger(), nullable=True))
    op.add_column(
        "bookings", sa.Column("internal_notes", sa.Text(), nullable=False, server_default="")
    )


def downgrade() -> None:
    op.drop_column("bookings", "internal_notes")
    op.drop_column("bookings", "refund_due")
