"""Piyasa takvimi API cikti semalari."""

from datetime import date

from pydantic import BaseModel


class CalendarEventOut(BaseModel):
    id: str
    date: date
    type: str
    type_label: str
    title: str
    detail: str | None = None
    source: str
    tickers: list[str] = []
    disclosure_index: int | None = None
    upcoming: bool = False
