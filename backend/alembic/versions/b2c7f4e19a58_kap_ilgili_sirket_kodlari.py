"""KAP bildirimlerine `relatedStocks` kodlarini ekler.

Collector yalniz `stockCodes`'u okuyordu; Borsa Istanbul (devre kesici, islem
sirasi), KAP (pay alim satim, SPK kararlari) ve derecelendirme kuruluslarinin
baska bir sirket hakkindaki bildirimleri bu yuzden hisseye baglanmiyordu.
Collector artik iki alani birlestiriyor; bu migration kayitli satirlari ham
liste kaydindan (`raw_list_item`) ayni kurala getirir. Yayincinin kodlari onde
kalir, eksik ilgili sirket kodlari sirasiyla sona eklenir. Tekrar calistirmak
zararsizdir.

Revision ID: b2c7f4e19a58
Revises: a3f9d2c7e1b4
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2c7f4e19a58"
down_revision: str | None = "a3f9d2c7e1b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Ayiraclar `app.collectors.kap.parse_ticker_codes` ile ayni.
_BACKFILL = r"""
UPDATE kap_disclosure AS d
SET ticker_codes = d.ticker_codes || extra.codes
FROM (
    SELECT k.disclosure_index, jsonb_agg(t.code ORDER BY t.position) AS codes
    FROM kap_disclosure AS k
    CROSS JOIN LATERAL (
        SELECT part.code, MIN(part.position) AS position
        FROM regexp_split_to_table(
            upper(trim(k.raw_list_item ->> 'relatedStocks')), '[,;/\s]+'
        ) WITH ORDINALITY AS part(code, position)
        WHERE part.code NOT IN ('', '-')
        GROUP BY part.code
    ) AS t
    WHERE coalesce(k.raw_list_item ->> 'relatedStocks', '') <> ''
      AND NOT k.ticker_codes @> jsonb_build_array(t.code)
    GROUP BY k.disclosure_index
) AS extra
WHERE d.disclosure_index = extra.disclosure_index
"""


def upgrade() -> None:
    op.execute(_BACKFILL)


def downgrade() -> None:
    # Veri tamamlama geri alinmaz; eski kural kodlari zaten eksik birakiyordu.
    pass
