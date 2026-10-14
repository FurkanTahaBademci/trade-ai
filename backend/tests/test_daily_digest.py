"""Gunluk ozet mesaji ve gonderim kosullari (ag/DB yok)."""

from datetime import date
from types import SimpleNamespace

from app.alerts import digest
from app.alerts.digest import DigestData, build_daily_digest


def test_digest_message_uses_turkish_formatting_and_lists_trades():
    message = build_daily_digest(
        DigestData(
            as_of=date(2026, 10, 14),
            index_value=10234.56,
            index_change_pct=1.234,
            portfolio_equity=877626.65,
            portfolio_day_pct=-0.42,
            portfolio_total_pct=-12.24,
            buys=["ASELS"],
            sells=[("MAVI", "stop_loss")],
            risers=[("CCCC", 76.0, 85.0)],
            fallers=[("AAAA", 80.0, 60.0)],
            top=[("RGYAS", 77.0, "VERY_POSITIVE")],
        )
    )

    assert message.event_type == "daily_digest"
    assert message.title == "📊 BIST günlük özet · 14.10.2026"
    lines = message.message.splitlines()
    assert lines[0] == "BIST100: 10.234,56 (+%1,2)"
    assert lines[1] == "Paper portföy: ₺877.627 · gün −%0,4 · toplam −%12,2"
    assert lines[2] == "İşlemler: AL ASELS, SAT MAVI (zarar-kes)"
    assert "Skoru yükselen: CCCC 76→85" in lines
    assert "Skoru düşen: AAAA 80→60" in lines
    assert "En yüksek skor: RGYAS 77 (Çok olumlu)" in lines
    assert lines[-1].endswith("yatırım tavsiyesi değildir.")


def test_tiny_changes_are_shown_without_a_sign():
    message = build_daily_digest(
        DigestData(as_of=date(2026, 10, 14), index_value=10000.0, index_change_pct=-0.04)
    )
    assert message.message.splitlines()[0] == "BIST100: 10.000,00 (%0,0)"


def test_digest_without_portfolio_or_movers_stays_short():
    message = build_daily_digest(DigestData(as_of=date(2026, 10, 14), index_value=10000.0))
    assert message.message.splitlines()[:2] == ["BIST100: 10.000,00", "İşlemler: yok"]


async def test_digest_job_is_opt_in(monkeypatch):
    async def settings():
        return SimpleNamespace(alerts_daily_digest_enabled=False, alerts_enabled=True)

    monkeypatch.setattr(digest, "resolve_settings", settings)
    assert await digest.send_daily_digest({}) == {"status": "disabled"}
