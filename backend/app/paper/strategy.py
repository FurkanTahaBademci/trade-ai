"""Strateji portfoyu ayarlari: dogrulama, hazir sablonlar ve motor parametreleri.

Kullanici yalniz karar esiklerini ve risk kurallarini secer. Komisyon, fiyat
kaymasi, tavan/taban ve dusuk hacim kurallari herkes icin aynidir; boylece
farkli portfoylerin sonuclari ayni gerceklik varsayimlariyla karsilastirilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.paper.risk import RiskConfig


@dataclass(frozen=True)
class StrategyParams:
    """Giris/cikis kararlarinin esikleri (varsayilanlar model portfoyle ayni)."""

    entry_score: Decimal = Decimal(75)
    exit_score: Decimal = Decimal(55)
    min_confidence: Decimal = Decimal("0.25")
    min_coverage: int = 2
    max_positions: int = 10
    max_new_entries_per_day: int = 3


DEFAULT_PARAMS = StrategyParams()


def _decimal(value: float) -> Decimal:
    # 75.0 -> Decimal(75): islem gerekcesinde "≥ 75" yazsin, "75.0" degil.
    return Decimal(int(value)) if float(value).is_integer() else Decimal(str(value))


class StrategyConfig(BaseModel):
    """`paper_portfolio.config` JSON'u; API'de de ayni sema kullanilir."""

    entry_score: float = Field(default=75, ge=50, le=100)
    exit_score: float = Field(default=55, ge=0, le=95)
    min_confidence: float = Field(default=0.25, ge=0, le=1)
    min_coverage: int = Field(default=2, ge=1, le=4)
    max_positions: int = Field(default=10, ge=1, le=30)
    max_new_entries_per_day: int = Field(default=3, ge=1, le=30)
    max_position_weight_pct: float = Field(default=10, gt=0, le=50)
    # 0 = sinirsiz
    max_sector_weight_pct: float = Field(default=30, ge=0, le=100)
    stop_loss_pct: float = Field(default=15, ge=0, lt=100)
    take_profit_pct: float = Field(default=0, ge=0, le=500)
    trailing_stop_pct: float = Field(default=0, ge=0, lt=100)
    rebalance_enabled: bool = True

    @model_validator(mode="after")
    def validate_ranges(self) -> StrategyConfig:
        if self.exit_score >= self.entry_score:
            raise ValueError("Çıkış skoru giriş skorundan küçük olmalı.")
        if self.max_positions * self.max_position_weight_pct > 100:
            raise ValueError("Pozisyon sayısı × tek pozisyon ağırlığı %100'ü aşamaz.")
        return self

    def params(self) -> StrategyParams:
        return StrategyParams(
            entry_score=_decimal(self.entry_score),
            exit_score=_decimal(self.exit_score),
            min_confidence=_decimal(self.min_confidence),
            min_coverage=self.min_coverage,
            max_positions=self.max_positions,
            max_new_entries_per_day=self.max_new_entries_per_day,
        )

    def risk(self) -> RiskConfig:
        return RiskConfig(
            stop_loss_pct=_decimal(self.stop_loss_pct),
            take_profit_pct=_decimal(self.take_profit_pct),
            trailing_stop_pct=_decimal(self.trailing_stop_pct),
            max_position_weight=_decimal(self.max_position_weight_pct) / 100,
            max_sector_weight=_decimal(self.max_sector_weight_pct) / 100,
            rebalance_enabled=self.rebalance_enabled,
        )


TemplateName = Literal["model", "temkinli", "agresif"]


@dataclass(frozen=True)
class StrategyTemplate:
    key: TemplateName
    label: str
    description: str
    config: StrategyConfig


TEMPLATES: dict[str, StrategyTemplate] = {
    template.key: template
    for template in (
        StrategyTemplate(
            "model",
            "Model stratejisi",
            "Herkese açık model portföyün kuralları: skor 75 üstünde al, 55 altında sat, "
            "en çok 10 pozisyon, %15 zarar-kes.",
            StrategyConfig(),
        ),
        StrategyTemplate(
            "temkinli",
            "Temkinli",
            "Yalnız en güçlü sinyaller (80+), daha erken çıkış (60 altı), %10 zarar-kes ve "
            "%10 takip eden stop; daha az ve dağıtık pozisyon.",
            StrategyConfig(
                entry_score=80,
                exit_score=60,
                min_confidence=0.4,
                max_positions=8,
                max_new_entries_per_day=2,
                max_sector_weight_pct=25,
                stop_loss_pct=10,
                trailing_stop_pct=10,
            ),
        ),
        StrategyTemplate(
            "agresif",
            "Agresif",
            "Daha fazla sinyale girer (70+), geç çıkar (50 altı), en çok 15 küçük pozisyon "
            "ve %20 zarar-kes.",
            StrategyConfig(
                entry_score=70,
                exit_score=50,
                max_positions=15,
                max_new_entries_per_day=5,
                max_position_weight_pct=6.5,
                max_sector_weight_pct=40,
                stop_loss_pct=20,
            ),
        ),
    )
}
