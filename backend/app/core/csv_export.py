"""Turkce Excel uyumlu CSV uretimi (UTF-8 BOM, noktali virgul) ve formul enjeksiyonu korumasi."""

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi.responses import Response

BOM = "﻿"
DELIMITER = ";"
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value: str) -> str:
    """`=`, `+`, `-`, `@` ile baslayan metni (bosluk atlanarak) tek tirnakla etkisizlestirir."""
    if value.lstrip(" ").startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Evet" if value else "Hayır"
    # Sayilar sanitize edilmez (negatif sayi formul degildir); ondalik ayraci virgul.
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, "f").replace(".", ",")
    if isinstance(value, float):
        return repr(value).replace(".", ",")
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return sanitize_cell(str(value))


def build_csv(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=DELIMITER, lineterminator="\r\n")
    writer.writerow([sanitize_cell(h) for h in headers])
    for row in rows:
        writer.writerow([format_cell(cell) for cell in row])
    return (BOM + buffer.getvalue()).encode("utf-8")


def csv_response(filename: str, headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> Response:
    return Response(
        content=build_csv(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
