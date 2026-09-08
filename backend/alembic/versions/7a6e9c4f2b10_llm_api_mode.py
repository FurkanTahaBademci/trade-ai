"""LLM istek API yolunu denetlenebilir yap.

Revision ID: 7a6e9c4f2b10
Revises: 4bd6dc234c85
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7a6e9c4f2b10"
down_revision: str | None = "4bd6dc234c85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "llm_evaluation",
        sa.Column(
            "api_mode",
            sa.String(length=32),
            nullable=False,
            server_default="generate_content",
        ),
    )
    op.create_check_constraint(
        "ck_llm_evaluation_api_mode",
        "llm_evaluation",
        "api_mode IN ('interactions', 'generate_content')",
    )
    op.alter_column("llm_evaluation", "api_mode", server_default="interactions")


def downgrade() -> None:
    op.drop_constraint(
        "ck_llm_evaluation_api_mode",
        "llm_evaluation",
        type_="check",
    )
    op.drop_column("llm_evaluation", "api_mode")
