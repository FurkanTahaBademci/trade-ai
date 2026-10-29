"""SQLAlchemy modelleri.

Her yeni model dosyasi burada import edilmeli ki Alembic autogenerate
onu görsün (bkz. alembic/env.py -> target_metadata).
"""

from app.core.db import Base
from app.models.backtest import BacktestRun, BacktestRunPoint, BacktestRunTrade
from app.models.fundamental import FinancialFact, FundamentalSnapshot
from app.models.index_price import IndexDaily
from app.models.institutional import (
    AnalystConsensus,
    AnalystRecommendation,
    FundFlowAggregate,
    FundSnapshot,
)
from app.models.instrument import Instrument
from app.models.kap import KapAttachment, KapDisclosure
from app.models.llm_evaluation import LlmEvaluation
from app.models.macro import MacroSeriesPoint, MonetaryPolicyDecision
from app.models.news import NewsArticle
from app.models.paper import (
    PaperOrder,
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperPosition,
    PaperTrade,
)
from app.models.price import PriceDaily
from app.models.schedule import CollectorSchedule, ScheduleAuditLog
from app.models.signal import CompositeSignalSnapshot
from app.models.user import AppUser, InviteCode, UserSession, UserToken, UserWatchlistItem
from app.models.watchlist import WatchlistItem

__all__ = [
    "AnalystConsensus",
    "AnalystRecommendation",
    "AppUser",
    "BacktestRun",
    "BacktestRunPoint",
    "BacktestRunTrade",
    "Base",
    "CollectorSchedule",
    "CompositeSignalSnapshot",
    "FinancialFact",
    "FundFlowAggregate",
    "FundSnapshot",
    "FundamentalSnapshot",
    "IndexDaily",
    "Instrument",
    "InviteCode",
    "KapAttachment",
    "KapDisclosure",
    "LlmEvaluation",
    "MacroSeriesPoint",
    "MonetaryPolicyDecision",
    "NewsArticle",
    "PaperOrder",
    "PaperPortfolio",
    "PaperPortfolioSnapshot",
    "PaperPosition",
    "PaperTrade",
    "PriceDaily",
    "ScheduleAuditLog",
    "UserSession",
    "UserToken",
    "UserWatchlistItem",
    "WatchlistItem",
]
