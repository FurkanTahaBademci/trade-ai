"""Haber basligi/ozetinde cozulmeden kalan HTML entity'lerini temizler.

Dunya ve Foreks RSS'i CDATA icine entity koyuyordu; collector artik bunlari
cozuyor. Bu migration daha once kaydedilmis satirlari ayni hale getirir.
Tekrar calistirmak zararsizdir.

Revision ID: c7d2e94f1a03
Revises: b5e1d7a39c24
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c7d2e94f1a03"
down_revision: str | None = "b5e1d7a39c24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# `&amp;` en sonda: once `&amp;#039;` gibi cift kodlananlar `&#039;`e iner.
_REPLACEMENTS = (
    ("&amp;", "&"),
    ("&#039;", "'"),
    ("&#39;", "'"),
    ("&quot;", '"'),
    ("&lt;", "<"),
    ("&gt;", ">"),
)


def _decode(column: str) -> str:
    expression = column
    for old, new in _REPLACEMENTS:
        expression = f"REPLACE({expression}, '{old}', '{new.replace(chr(39), chr(39) * 2)}')"
    return expression


def upgrade() -> None:
    for column in ("title", "summary"):
        op.execute(
            f"UPDATE news_article SET {column} = {_decode(column)} "
            f"WHERE {column} LIKE '%&%;%'"
        )


def downgrade() -> None:
    # Veri temizligi geri alinmaz.
    pass
