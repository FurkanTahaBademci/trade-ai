"""Sik okunan listeler icin indeksler.

- llm_evaluation (created_at DESC, id DESC): AI analizleri listesi en yeniden
  eskiye sayfalanir; indekssiz her istekte tum tablo taranip siralaniyordu.
- llm_evaluation (completed_at) WHERE status = 'succeeded': gunluk token
  butcesi (10 dakikada bir) ve saglayici duraklatma kontrolu bugunun basarili
  kayitlarini toplar; kismi indeksle tum tablo yerine yalniz bugunku satirlar
  okunur.

Revision ID: d4b8e2f1a6c3
Revises: c1e6a8d27f49
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4b8e2f1a6c3"
down_revision: str | None = "c1e6a8d27f49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_llm_evaluation_created_id",
        "llm_evaluation",
        [sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_llm_evaluation_succeeded_completed",
        "llm_evaluation",
        ["completed_at"],
        postgresql_where=sa.text("status = 'succeeded'"),
    )


def downgrade() -> None:
    op.drop_index("ix_llm_evaluation_succeeded_completed", table_name="llm_evaluation")
    op.drop_index("ix_llm_evaluation_created_id", table_name="llm_evaluation")
