"""Kullanicinin kendi bildirimleri: Telegram baglama, anlik etiket degisimi, gunluk ozet.

- Baglama: kullanici sitede tek kullanimlik kod alir ve `t.me/<bot>?start=<kod>`
  ile bot'a yazar. Worker dakikada bir getUpdates ile mesajlari okur, kodu
  hesaba baglar. `/stop` baglantiyi kaldirir.
- Anlik bildirim: izleme listesindeki ya da kendi aktif portfoylerinde tutulan
  hisselerin skor etiketi degisince Telegram'a tek mesaj gider (10 dakikada bir).
- Gunluk ozet: islem gunu sonunda portfoy degeri, gunun islemleri, reddedilen
  emirler ve izlenen hisselerdeki etiket degisimleri; Telegram ve/veya e-posta.
  `last_digest_on` ayni gun icin ikinci gonderimi engeller.

Model portfoy ve yonetici bildirimleri `service.py` / `digest.py`'dedir.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import structlog
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.digest import BENCHMARK_INDEX, EXIT_TEXT, _number, _signed_pct
from app.alerts.service import EVENT_TTL_SECONDS, LABEL_TEXT, _load_scores, detect_label_changes
from app.alerts.telegram import bot_username, get_updates, send_text
from app.auth.service import consume_token, issue_token, utcnow
from app.core.config import Settings
from app.mail.sender import OutgoingMail, enqueue_mail, mask_email
from app.models import (
    AppUser,
    CompositeSignalSnapshot,
    IndexDaily,
    PaperOrder,
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperPosition,
    PaperTrade,
    UserAlertPref,
    UserWatchlistItem,
)
from app.signals.service import MODEL_VERSION as SIGNAL_MODEL_VERSION

logger = structlog.get_logger(__name__)

LINK_TOKEN_TTL = timedelta(minutes=30)
POLL_LOCK_KEY = "telegram:poll:lock"
POLL_OFFSET_KEY = "telegram:poll:offset"
# Bot'ta webhook varken getUpdates 409 doner; her dakika denememek icin ara verilir.
POLL_PAUSE_KEY = "telegram:poll:paused"
POLL_PAUSE_SECONDS = 15 * 60
USER_LABEL_STATE_KEY = "alerts:user_label_state"
MAX_ALERT_LINES = 20
# Veri toplama durduysa eski gunun ozeti gonderilmez.
DIGEST_MAX_AGE = timedelta(days=4)
DISCLAIMER = "Bilgi amaçlıdır; yatırım tavsiyesi değildir."

WELCOME_TEXT = (
    "Merhaba! Bu bot trade-ai hesabına bağlanınca izlediğin hisseler ve paper "
    "portföylerin için bildirim gönderir.\n"
    "Bağlamak için sitede Hesabım → Bildirimler sayfasındaki “Telegram'ı bağla” "
    "düğmesini kullan. Bağlantıyı kaldırmak için /stop yaz."
)
INVALID_CODE_TEXT = (
    "Bu bağlantı kodu geçersiz ya da süresi dolmuş. Sitedeki Bildirimler sayfasından "
    "yeni bir bağlantı oluştur."
)
STOPPED_TEXT = "Bağlantı kaldırıldı; bu sohbete artık bildirim gönderilmeyecek."
NOT_LINKED_TEXT = "Bu sohbet bir trade-ai hesabına bağlı değil."


def telegram_ready(settings: Settings) -> bool:
    return settings.user_alerts_enabled and bool(settings.alerts_telegram_bot_token)


async def get_pref(db: AsyncSession, user_id: int, *, create: bool = False) -> UserAlertPref | None:
    pref = await db.get(UserAlertPref, user_id)
    if pref is None and create:
        pref = UserAlertPref(
            user_id=user_id, telegram_instant=True, telegram_digest=True, email_digest=False
        )
        db.add(pref)
        await db.flush()
    return pref


async def unlink_chat(db: AsyncSession, chat_id: str) -> int:
    result = await db.execute(
        update(UserAlertPref)
        .where(UserAlertPref.telegram_chat_id == chat_id)
        .values(telegram_chat_id=None, telegram_username=None, telegram_linked_at=None)
    )
    return result.rowcount or 0


# --- Telegram baglama -------------------------------------------------------


async def create_link(
    db: AsyncSession, user: AppUser, *, settings: Settings, redis: Redis, client: httpx.AsyncClient
) -> tuple[str, datetime] | None:
    """Derin baglanti ve son gecerlilik zamani; bot hazir degilse None."""
    if not telegram_ready(settings):
        return None
    username = await bot_username(client, settings.alerts_telegram_bot_token, redis)
    if username is None:
        return None
    code = await issue_token(db, user, "TELEGRAM_LINK", LINK_TOKEN_TTL)
    await db.commit()
    return f"https://t.me/{username}?start={code}", utcnow() + LINK_TOKEN_TTL


async def handle_update(db: AsyncSession, update_body: dict[str, Any]) -> tuple[str, str] | None:
    """Bot'a gelen tek mesaji isler; yanitlanacaksa (chat_id, metin) doner."""
    message = update_body.get("message") or {}
    chat = message.get("chat") or {}
    if chat.get("type") != "private" or "id" not in chat:
        return None
    chat_id = str(chat["id"])
    command, _, argument = (message.get("text") or "").strip().partition(" ")
    command = command.split("@", 1)[0].lower()
    if command == "/start":
        code = argument.strip()
        if not code:
            return chat_id, WELCOME_TEXT
        user = await consume_token(db, code, "TELEGRAM_LINK") if len(code) <= 64 else None
        if user is None:
            return chat_id, INVALID_CODE_TEXT
        pref = await get_pref(db, user.id, create=True)
        assert pref is not None
        username = (message.get("from") or {}).get("username")
        pref.telegram_chat_id = chat_id
        pref.telegram_username = str(username)[:64] if username else None
        pref.telegram_linked_at = utcnow()
        await db.commit()
        logger.info("telegram_linked", user_id=user.id)
        return chat_id, (
            f"✅ trade-ai hesabın bağlandı ({mask_email(user.email)}). Bildirim "
            "tercihlerini sitede Hesabım → Bildirimler'den değiştirebilirsin. "
            "Bağlantıyı kaldırmak için /stop yaz."
        )
    if command == "/stop":
        removed = await unlink_chat(db, chat_id)
        await db.commit()
        return chat_id, STOPPED_TEXT if removed else NOT_LINKED_TEXT
    if command in {"/help", "/yardim"}:
        return chat_id, WELCOME_TEXT
    return None


async def poll_telegram(
    factory: Callable[[], Any], *, settings: Settings, redis: Redis, client: httpx.AsyncClient
) -> dict[str, Any]:
    """Bot'a gelen mesajlari okur ve isler. Ayni anda tek sorgu (Redis kilidi)."""
    if not telegram_ready(settings):
        return {"status": "disabled"}
    if await redis.get(POLL_PAUSE_KEY):
        return {"status": "paused"}
    if not await redis.set(POLL_LOCK_KEY, "1", nx=True, ex=60):
        return {"status": "busy"}
    token = settings.alerts_telegram_bot_token
    try:
        offset = await redis.get(POLL_OFFSET_KEY)
        updates, error = await get_updates(client, token, int(offset) if offset else None)
        if error:
            if error == "conflict":
                await redis.set(POLL_PAUSE_KEY, "conflict", ex=POLL_PAUSE_SECONDS)
            logger.warning("telegram_poll_failed", error=error)
            return {"status": "error", "error": error}
        handled = 0
        for item in updates:
            try:
                async with factory() as db:
                    reply = await handle_update(db, item)
                if reply is not None:
                    await send_text(client, token, *reply)
                handled += 1
            except Exception as exc:  # noqa: BLE001 - tek bozuk mesaj kuyrugu tikamasin
                logger.error("telegram_update_failed", error=str(exc)[:200])
            # Islenen guncelleme bir sonraki sorguda Telegram'dan silinir.
            await redis.set(POLL_OFFSET_KEY, int(item.get("update_id", 0)) + 1)
        return {"status": "ok", "updates": len(updates), "handled": handled}
    finally:
        await redis.delete(POLL_LOCK_KEY)


# --- Anlik etiket degisimi -------------------------------------------------


@dataclass
class Recipient:
    chat_id: str
    watched: set[str] = field(default_factory=set)
    held: set[str] = field(default_factory=set)


async def _tracked_tickers(
    db: AsyncSession, user_ids: list[int], tickers: set[str] | None = None
) -> tuple[dict[int, set[str]], dict[int, set[str]]]:
    """Kullanici basina izleme listesi ve aktif portfoylerde tutulan hisseler."""
    watch_stmt = select(UserWatchlistItem.user_id, UserWatchlistItem.ticker).where(
        UserWatchlistItem.user_id.in_(user_ids)
    )
    held_stmt = (
        select(PaperPortfolio.owner_id, PaperPosition.ticker)
        .join(PaperPortfolio, PaperPortfolio.id == PaperPosition.portfolio_id)
        .where(PaperPortfolio.owner_id.in_(user_ids), PaperPortfolio.status == "ACTIVE")
    )
    if tickers is not None:
        watch_stmt = watch_stmt.where(UserWatchlistItem.ticker.in_(tickers))
        held_stmt = held_stmt.where(PaperPosition.ticker.in_(tickers))
    watched: dict[int, set[str]] = {}
    held: dict[int, set[str]] = {}
    for user_id, ticker in (await db.execute(watch_stmt)).all():
        watched.setdefault(user_id, set()).add(ticker)
    for user_id, ticker in (await db.execute(held_stmt)).all():
        held.setdefault(user_id, set()).add(ticker)
    return watched, held


async def instant_recipients(db: AsyncSession, tickers: set[str]) -> dict[int, Recipient]:
    rows = (
        await db.execute(
            select(UserAlertPref.user_id, UserAlertPref.telegram_chat_id)
            .join(AppUser, AppUser.id == UserAlertPref.user_id)
            .where(
                UserAlertPref.telegram_chat_id.is_not(None),
                UserAlertPref.telegram_instant.is_(True),
                AppUser.status == "ACTIVE",
            )
        )
    ).all()
    if not rows or not tickers:
        return {}
    chats = {user_id: chat_id for user_id, chat_id in rows}
    watched, held = await _tracked_tickers(db, list(chats), tickers)
    return {
        user_id: Recipient(chat_id, watched.get(user_id, set()), held.get(user_id, set()))
        for user_id, chat_id in chats.items()
        if watched.get(user_id) or held.get(user_id)
    }


def format_label_alert(changes: list[dict[str, Any]], held: set[str]) -> str:
    lines = ["🔔 İzlediğin hisselerde skor etiketi değişti"]
    for change in changes[:MAX_ALERT_LINES]:
        old = LABEL_TEXT.get(change["from"], change["from"])
        new = LABEL_TEXT.get(change["to"], change["to"])
        suffix = " · portföyünde" if change["ticker"] in held else ""
        lines.append(f"{change['ticker']}: {old} → {new} ({_number(change['score'], 1)}){suffix}")
    if len(changes) > MAX_ALERT_LINES:
        lines.append(f"…ve {len(changes) - MAX_ALERT_LINES} hisse daha")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


async def evaluate_user_label_alerts(
    db: AsyncSession,
    *,
    settings: Settings,
    redis: Redis,
    client: httpx.AsyncClient,
    loaded: tuple[date | None, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, int]:
    """Etiketi degisen hisseleri, onlari izleyen/tutan kullanicilara tek mesajla bildirir.

    Etiket durumu tum hisseler icin Redis'te tutulur; ilk gozlem bildirim degildir.
    Telegram tamamen ulasilamazsa durum ilerletilmez, sonraki turda yeniden denenir.
    """
    stats = {"user_label_alerts": 0, "user_label_failures": 0}
    if not telegram_ready(settings):
        return stats
    as_of, current = loaded if loaded is not None else await _load_scores(db)
    if as_of is None:
        return stats
    previous = await redis.hgetall(USER_LABEL_STATE_KEY)
    changes = {change["ticker"]: change for change in detect_label_changes(previous, current)}
    recipients = await instant_recipients(db, set(changes)) if changes else {}
    token = settings.alerts_telegram_bot_token
    for user_id, recipient in recipients.items():
        items = [changes[t] for t in sorted(recipient.watched | recipient.held)]
        fingerprint = ";".join(f"{c['ticker']}:{c['from']}:{c['to']}" for c in items)
        key = (
            "alerts:sent:user:"
            + hashlib.sha256(f"{user_id}:{as_of.isoformat()}:{fingerprint}".encode()).hexdigest()
        )
        if not await redis.set(key, "1", ex=EVENT_TTL_SECONDS, nx=True):
            continue
        result = await send_text(
            client, token, recipient.chat_id, format_label_alert(items, recipient.held)
        )
        if result.ok:
            stats["user_label_alerts"] += 1
        else:
            await redis.delete(key)
            if result.blocked:
                await unlink_chat(db, recipient.chat_id)
                await db.commit()
            else:
                stats["user_label_failures"] += 1
                logger.warning("user_alert_failed", user_id=user_id, error=result.error)
        await asyncio.sleep(0.05)  # Telegram: saniyede ~30 mesaj siniri
    delivered_nothing = stats["user_label_failures"] and not stats["user_label_alerts"]
    state = {
        ticker: row["label"]
        for ticker, row in current.items()
        if not (delivered_nothing and ticker in changes)
    }
    if state:
        await redis.hset(USER_LABEL_STATE_KEY, mapping=state)
    return stats


# --- Gunluk ozet -------------------------------------------------------------


@dataclass
class PortfolioDigest:
    name: str
    equity: float | None = None
    day_pct: float | None = None
    total_pct: float | None = None
    buys: list[str] = field(default_factory=list)
    sells: list[tuple[str, str | None]] = field(default_factory=list)
    rejected: list[tuple[str, str, str]] = field(default_factory=list)  # yon, hisse, sebep


@dataclass
class UserDigest:
    as_of: date
    index_value: float | None = None
    index_change_pct: float | None = None
    portfolios: list[PortfolioDigest] = field(default_factory=list)
    label_changes: list[tuple[str, str, str, float]] = field(default_factory=list)
    watch_count: int = 0

    @property
    def empty(self) -> bool:
        return not self.portfolios and not self.label_changes


def build_user_digest(digest: UserDigest) -> str:
    lines = [f"📊 trade-ai günlük özetin · {digest.as_of:%d.%m.%Y}"]
    if digest.index_value is not None:
        change = (
            f" ({_signed_pct(digest.index_change_pct)})"
            if digest.index_change_pct is not None
            else ""
        )
        lines.append(f"BIST100: {_number(digest.index_value, 2)}{change}")
    for item in digest.portfolios:
        lines.append("")
        parts = [f"₺{_number(item.equity)}"] if item.equity is not None else []
        if item.day_pct is not None:
            parts.append(f"gün {_signed_pct(item.day_pct)}")
        if item.total_pct is not None:
            parts.append(f"toplam {_signed_pct(item.total_pct)}")
        lines.append(f"{item.name}: " + (" · ".join(parts) if parts else "değerleme yok"))
        trades = [f"AL {ticker}" for ticker in item.buys]
        trades += [
            f"SAT {ticker}" + (f" ({EXIT_TEXT.get(reason, reason)})" if reason else "")
            for ticker, reason in item.sells
        ]
        lines.append("İşlemler: " + (", ".join(trades) if trades else "yok"))
        for side, ticker, reason in item.rejected:
            lines.append(f"Reddedilen emir: {'AL' if side == 'BUY' else 'SAT'} {ticker} — {reason}")
    lines.append("")
    if digest.label_changes:
        lines.append("İzlediğin hisselerde etiket değişimi:")
        lines += [
            f"{ticker}: {LABEL_TEXT.get(old, old)} → {LABEL_TEXT.get(new, new)} "
            f"({_number(score, 1)})"
            for ticker, old, new, score in digest.label_changes[:MAX_ALERT_LINES]
        ]
    elif digest.watch_count:
        lines.append(f"İzlediğin {digest.watch_count} hissede etiket değişimi yok.")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


async def _index_close(
    db: AsyncSession,
) -> tuple[date | None, date | None, float | None, float | None]:
    rows = (
        await db.execute(
            select(IndexDaily.date, IndexDaily.value)
            .where(IndexDaily.index_code == BENCHMARK_INDEX)
            .order_by(IndexDaily.date.desc())
            .limit(2)
        )
    ).all()
    if not rows:
        return None, None, None, None
    value = float(rows[0].value)
    previous = rows[1] if len(rows) > 1 else None
    change = (value / float(previous.value) - 1) * 100 if previous and previous.value else None
    return rows[0].date, previous.date if previous else None, value, change


async def _labels_on(db: AsyncSession, tickers: set[str], on_or_before: date) -> dict[str, Any]:
    snapshot_date = await db.scalar(
        select(func.max(CompositeSignalSnapshot.as_of_date)).where(
            CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION,
            CompositeSignalSnapshot.as_of_date <= on_or_before,
        )
    )
    if snapshot_date is None or not tickers:
        return {}
    rows = await db.execute(
        select(
            CompositeSignalSnapshot.ticker,
            CompositeSignalSnapshot.signal_label,
            CompositeSignalSnapshot.composite_score,
        ).where(
            CompositeSignalSnapshot.model_version == SIGNAL_MODEL_VERSION,
            CompositeSignalSnapshot.as_of_date == snapshot_date,
            CompositeSignalSnapshot.ticker.in_(tickers),
        )
    )
    return {row.ticker: row for row in rows.all()}


async def _portfolio_digest(
    db: AsyncSession, portfolio: PaperPortfolio, as_of: date, since: datetime
) -> PortfolioDigest:
    item = PortfolioDigest(name=portfolio.name)
    snapshots = (
        await db.scalars(
            select(PaperPortfolioSnapshot)
            .where(
                PaperPortfolioSnapshot.portfolio_id == portfolio.id,
                PaperPortfolioSnapshot.snapshot_date <= as_of,
            )
            .order_by(PaperPortfolioSnapshot.snapshot_date.desc())
            .limit(2)
        )
    ).all()
    if snapshots and snapshots[0].snapshot_date == as_of:
        item.equity = float(snapshots[0].total_equity)
        item.total_pct = float(snapshots[0].total_return_pct)
        if len(snapshots) > 1 and snapshots[1].total_equity:
            item.day_pct = (item.equity / float(snapshots[1].total_equity) - 1) * 100
    trades = await db.execute(
        select(PaperTrade.ticker, PaperTrade.side, PaperTrade.exit_reason)
        .where(PaperTrade.portfolio_id == portfolio.id, PaperTrade.trade_date == as_of)
        .order_by(PaperTrade.id)
    )
    for trade in trades.all():
        if trade.side == "BUY":
            item.buys.append(trade.ticker)
        else:
            item.sells.append((trade.ticker, trade.exit_reason))
    rejected = await db.execute(
        select(PaperOrder.side, PaperOrder.ticker, PaperOrder.note)
        .where(
            PaperOrder.portfolio_id == portfolio.id,
            PaperOrder.status == "REJECTED",
            PaperOrder.updated_at >= since,
        )
        .order_by(PaperOrder.id)
    )
    item.rejected = [(row.side, row.ticker, row.note or "") for row in rejected.all()]
    return item


async def collect_user_digest(
    db: AsyncSession,
    user_id: int,
    *,
    as_of: date,
    previous_day: date | None,
    since: datetime,
) -> UserDigest:
    digest = UserDigest(as_of=as_of)
    portfolios = (
        await db.scalars(
            select(PaperPortfolio)
            .where(PaperPortfolio.owner_id == user_id, PaperPortfolio.status == "ACTIVE")
            .order_by(PaperPortfolio.id)
        )
    ).all()
    for portfolio in portfolios:
        digest.portfolios.append(await _portfolio_digest(db, portfolio, as_of, since))
    watched, held = await _tracked_tickers(db, [user_id])
    tickers = watched.get(user_id, set()) | held.get(user_id, set())
    digest.watch_count = len(tickers)
    if tickers and previous_day is not None:
        today = await _labels_on(db, tickers, as_of)
        before = await _labels_on(db, tickers, previous_day)
        digest.label_changes = [
            (ticker, before[ticker].signal_label, row.signal_label, float(row.composite_score))
            for ticker, row in sorted(today.items())
            if ticker in before and before[ticker].signal_label != row.signal_label
        ]
    return digest


async def send_user_digests(
    factory: Callable[[], Any],
    *,
    settings: Settings,
    client: httpx.AsyncClient,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Islem gunu ozetini abone kullanicilara gonderir; her kullanici gunde bir kez."""
    if not settings.user_alerts_enabled:
        return {"status": "disabled"}
    now = now or datetime.now(UTC)
    async with factory() as db:
        as_of, previous_day, index_value, index_change = await _index_close(db)
        if as_of is None:
            return {"status": "no_data"}
        if as_of < now.astimezone(ZoneInfo(settings.tz)).date() - DIGEST_MAX_AGE:
            return {"status": "stale", "as_of": as_of.isoformat()}
        # Duz satirlar: bir kullanicida rollback olursa digerlerinin verisi bayatlamasin.
        rows = (
            await db.execute(
                select(
                    AppUser.id,
                    AppUser.email,
                    UserAlertPref.telegram_chat_id,
                    UserAlertPref.telegram_digest,
                    UserAlertPref.email_digest,
                )
                .join(AppUser, AppUser.id == UserAlertPref.user_id)
                .where(
                    AppUser.status == "ACTIVE",
                    AppUser.email_verified_at.is_not(None),
                    UserAlertPref.email_digest.is_(True)
                    | (
                        UserAlertPref.telegram_digest.is_(True)
                        & UserAlertPref.telegram_chat_id.is_not(None)
                    ),
                    UserAlertPref.last_digest_on.is_(None) | (UserAlertPref.last_digest_on < as_of),
                )
                .order_by(AppUser.id)
            )
        ).all()
        stats = {"telegram": 0, "email": 0, "empty": 0, "failed": 0}
        token = settings.alerts_telegram_bot_token
        for row in rows:
            try:
                digest = await collect_user_digest(
                    db,
                    row.id,
                    as_of=as_of,
                    previous_day=previous_day,
                    since=now - timedelta(hours=24),
                )
                digest.index_value, digest.index_change_pct = index_value, index_change
                if digest.empty:
                    stats["empty"] += 1
                else:
                    text = build_user_digest(digest)
                    if row.telegram_digest and row.telegram_chat_id and token:
                        result = await send_text(client, token, row.telegram_chat_id, text)
                        if result.ok:
                            stats["telegram"] += 1
                        elif result.blocked:
                            await unlink_chat(db, row.telegram_chat_id)
                        else:
                            stats["failed"] += 1
                            logger.warning("user_digest_failed", user_id=row.id, error=result.error)
                    if row.email_digest and await enqueue_mail(
                        OutgoingMail(
                            to=row.email,
                            subject=f"trade-ai günlük özet · {as_of:%d.%m.%Y}",
                            text=text
                            + "\n\nBildirim tercihlerin: "
                            + f"{settings.public_base_url.rstrip('/')}/hesap/bildirimler",
                        )
                    ):
                        stats["email"] += 1
                await db.execute(
                    update(UserAlertPref)
                    .where(UserAlertPref.user_id == row.id)
                    .values(last_digest_on=as_of)
                )
                await db.commit()
            except Exception as exc:  # noqa: BLE001 - bir kullanicinin hatasi digerlerini durdurmasin
                await db.rollback()
                stats["failed"] += 1
                logger.error("user_digest_failed", user_id=row.id, error=str(exc)[:200])
            await asyncio.sleep(0.05)
    logger.info("user_digests", as_of=as_of.isoformat(), **stats)
    return {"status": "ok", "as_of": as_of.isoformat(), "recipients": len(rows), **stats}


async def send_test_message(
    pref: UserAlertPref, *, settings: Settings, client: httpx.AsyncClient
) -> bool:
    if not telegram_ready(settings) or not pref.telegram_chat_id:
        return False
    result = await send_text(
        client,
        settings.alerts_telegram_bot_token,
        pref.telegram_chat_id,
        "✅ trade-ai test bildirimi: bu sohbet hesabına bağlı.",
    )
    return result.ok
