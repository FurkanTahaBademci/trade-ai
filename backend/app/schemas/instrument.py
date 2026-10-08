"""Instrument ve fiyat verisi icin API cikti semalari."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str
    city: str | None
    is_active: bool
    updated_at: datetime


class PriceDailyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    close: float
    high: float | None
    low: float | None
    avg_price: float | None
    volume_try: float | None
    close_usd: float | None
    market_cap_try: float | None
