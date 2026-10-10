"""LLM degerlendirmesine 'filtered' durumu.

Kural tabanli on filtrenin eledigi haberler bu durumla kaydedilir; boylece
her dongude yeniden taranmaz ve Gemini'ye gonderilmez.

Revision ID: f2b8c6d14e57
Revises: e1a9b3c57d40
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f2b8c6d14e57"
down_revision: str | None = "e1a9b3c57d40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_llm_evaluation_status", "llm_evaluation", type_="check")
    op.create_check_constraint(
        "ck_llm_evaluation_status",
        "llm_evaluation",
        "status IN ('running', 'succeeded', 'failed', 'filtered')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM llm_evaluation WHERE status = 'filtered'")
    op.drop_constraint("ck_llm_evaluation_status", "llm_evaluation", type_="check")
    op.create_check_constraint(
        "ck_llm_evaluation_status",
        "llm_evaluation",
        "status IN ('running', 'succeeded', 'failed')",
    )
