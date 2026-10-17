"""Banka ve sigorta finansal tablolarini yeniden cekime al.

Finansal kurum tablolari (UFRS / UFRS_K) sanayi kalem kodlariyla okunuyordu;
ornegin bankada ozsermaye 2O iken 2N (satis amacli varlik borcu, 0) okundugu
icin PD/DD ve ROE bos, temel skor yanlis hesaplaniyordu. Kalemler tabloda
dogru oldugundan veri silinmez; yalniz `fetched_at` geri alinir. Boylece
collector bu hisseleri bir sonraki partide en once yeniden ceker ve
snapshot'lari yeni eslemeyle yeniden hesaplar.

Revision ID: a3f9d2c7e1b4
Revises: e5a7c3d9b1f4
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3f9d2c7e1b4"
down_revision: str | None = "e5a7c3d9b1f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE financial_fact SET fetched_at = TIMESTAMPTZ '2000-01-01 00:00:00+00' "
        "WHERE financial_group IN ('UFRS', 'UFRS_K')"
    )


def downgrade() -> None:
    # Yeniden cekim zamani geri alinamaz ve gerekmez; sonraki cekim gunceller.
    pass
