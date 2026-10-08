"""KAP uyesi basina birden cok hisse kodu destegi.

Revision ID: a7e2c4f98b11
Revises: 9c1f0d4a2e73
Create Date: 2026-09-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a7e2c4f98b11"
down_revision: str | None = "9c1f0d4a2e73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("instrument_kap_member_oid_key", "instrument", type_="unique")
    op.create_index("ix_instrument_kap_member_oid", "instrument", ["kap_member_oid"])


def downgrade() -> None:
    op.drop_index("ix_instrument_kap_member_oid", table_name="instrument")
    op.create_unique_constraint(
        "instrument_kap_member_oid_key",
        "instrument",
        ["kap_member_oid"],
    )
