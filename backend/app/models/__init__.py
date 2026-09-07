"""SQLAlchemy modelleri.

Her yeni model dosyasi burada import edilmeli ki Alembic autogenerate
onu görsün (bkz. alembic/env.py -> target_metadata).
"""

from app.core.db import Base
from app.models.fundamental import FinancialFact, FundamentalSnapshot
from app.models.institutional import (
    AnalystConsensus,
    AnalystRecommendation,
    FundFlowAggregate,
    FundSnapshot,
)
from app.models.instrument import Instrument
from app.models.kap import KapAttachment, KapDisclosure
from app.models.llm_evaluation import LlmEvaluation
from app.models.macro import MonetaryPolicyDecision
from app.models.news import NewsArticle
from app.models.paper import PaperPortfolio, PaperPortfolioSnapshot, PaperPosition, PaperTrade
from app.models.price import PriceDaily
from app.models.schedule import CollectorSchedule, ScheduleAuditLog
from app.models.signal import CompositeSignalSnapshot

__all__ = [
    "AnalystConsensus",
    "AnalystRecommendation",
    "Base",
    "CollectorSchedule",
    "CompositeSignalSnapshot",
    "FinancialFact",
    "FundFlowAggregate",
    "FundSnapshot",
    "FundamentalSnapshot",
    "Instrument",
    "KapAttachment",
    "KapDisclosure",
    "LlmEvaluation",
    "MonetaryPolicyDecision",
    "NewsArticle",
    "PaperPortfolio",
    "PaperPortfolioSnapshot",
    "PaperPosition",
    "PaperTrade",
    "PriceDaily",
    "ScheduleAuditLog",
]
