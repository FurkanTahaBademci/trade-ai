"""Collector schedule management.

Revision ID: c4e8a2b1d730
Revises: b7d4e9a2c610
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4e8a2b1d730"
down_revision: str | None = "b7d4e9a2c610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collector_schedule",
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("job_name", sa.String(96), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("minimum_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "interval_minutes >= minimum_interval_minutes",
            name="ck_schedule_interval_minimum",
        ),
        sa.CheckConstraint(
            "minimum_interval_minutes >= 1",
            name="ck_schedule_minimum_positive",
        ),
        sa.PrimaryKeyConstraint("name"),
        sa.UniqueConstraint("job_name"),
    )
    op.create_index("ix_collector_schedule_next_run_at", "collector_schedule", ["next_run_at"])

    op.create_table(
        "schedule_audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("schedule_name", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["schedule_name"], ["collector_schedule.name"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schedule_audit_log_schedule_name", "schedule_audit_log", ["schedule_name"])


def downgrade() -> None:
    op.drop_index("ix_schedule_audit_log_schedule_name", table_name="schedule_audit_log")
    op.drop_table("schedule_audit_log")
    op.drop_index("ix_collector_schedule_next_run_at", table_name="collector_schedule")
    op.drop_table("collector_schedule")
