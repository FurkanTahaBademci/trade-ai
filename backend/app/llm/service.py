"""Iki katmanli Gemini degerlendirme servisi.

Tier 1 tum yeni haber/KAP girdilerini hizli modelle siniflandirir. Tier 2,
yalniz yuksek etkili ve aktif BIST ticker'i ile eslesen girdileri daha derin
modelle inceler. Her cagri oncesi DB'de `running` kaydi commit edilir; basari,
hata ve token kullanimi ayni kayitta denetlenebilir kalir.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import httpx
import structlog
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import Settings, get_settings
from app.core.dynamic_settings import resolve_settings
from app.models import Instrument, KapDisclosure, LlmEvaluation, NewsArticle
from app.schemas.llm import (
    LlmTier1BatchResult,
    LlmTier1Result,
    LlmTier2Result,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md"
_PROMPT_SECTION_RE = re.compile(
    r"<!-- (?P<name>TIER[12]_SYSTEM) -->\s*(?P<body>.*?)\s*<!-- END_(?P=name) -->",
    re.DOTALL,
)
logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PromptBundle:
    tier1_system: str
    tier2_system: str


@dataclass(frozen=True)
class SourceDocument:
    source_type: str
    source_id: int
    published_at: datetime
    content_hash: str
    payload: dict


@dataclass(frozen=True)
class GatewayResponse:
    data: dict
    raw_text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class BatchEvaluationOutcome:
    attempted: int
    succeeded: int
    failed: int
    skipped: int
    input_tokens: int = 0
    output_tokens: int = 0


class LlmGateway(Protocol):
    async def generate(
        self,
        *,
        model: str,
        system_instruction: str,
        user_content: str,
        response_model: type[BaseModel],
        thinking_level: str,
        max_output_tokens: int,
    ) -> GatewayResponse: ...


def load_prompts(path: Path = PROMPT_PATH) -> PromptBundle:
    text = path.read_text(encoding="utf-8")
    sections = {match.group("name"): match.group("body").strip() for match in _PROMPT_SECTION_RE.finditer(text)}
    missing = {"TIER1_SYSTEM", "TIER2_SYSTEM"} - sections.keys()
    if missing:
        raise RuntimeError(f"Prompt bolumleri eksik: {sorted(missing)}")
    return PromptBundle(
        tier1_system=sections["TIER1_SYSTEM"],
        tier2_system=sections["TIER2_SYSTEM"],
    )


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _prompt_json(value: object) -> str:
    # Kaynak metnindeki sahte XML kapanis etiketleri delimiter'i delemesin.
    return _stable_json(value).replace("<", "\\u003c").replace(">", "\\u003e")


def content_hash(payload: dict) -> str:
    return hashlib.sha256(_stable_json(payload).encode()).hexdigest()


def evaluation_key(
    document: SourceDocument,
    *,
    tier: int,
    model: str,
    api_mode: str = "generate_content",
    prompt_version: str = PROMPT_VERSION,
    parent_key: str | None = None,
) -> str:
    identity = {
        "source_type": document.source_type,
        "source_id": document.source_id,
        "content_hash": document.content_hash,
        "prompt_version": prompt_version,
        "tier": tier,
        "model": model,
        "api_mode": api_mode,
        "parent_key": parent_key,
    }
    return hashlib.sha256(_stable_json(identity).encode()).hexdigest()


def _truncate(value: str | None, max_chars: int) -> str | None:
    if not value:
        return None
    text = value.strip()
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}\n[TRUNCATED]"


def document_from_news(article: NewsArticle, *, max_chars: int) -> SourceDocument:
    full_payload = {
        "source": article.source,
        "canonical_url": article.canonical_url,
        "published_at": article.published_at.isoformat(),
        "title": article.title,
        "summary": article.summary,
        "known_ticker_codes": article.ticker_codes,
    }
    input_payload = {
        **full_payload,
        "summary": _truncate(article.summary, max_chars),
    }
    return SourceDocument(
        source_type="news",
        source_id=article.id,
        published_at=article.published_at,
        content_hash=content_hash(full_payload),
        payload=input_payload,
    )


def document_from_kap(disclosure: KapDisclosure, *, max_chars: int) -> SourceDocument:
    full_payload = {
        "published_at": disclosure.published_at.isoformat(),
        "kap_title": disclosure.kap_title,
        "subject": disclosure.subject,
        "summary": disclosure.summary,
        "body_text": disclosure.body_text,
        "disclosure_class": disclosure.disclosure_class,
        "disclosure_type": disclosure.disclosure_type,
        "disclosure_category": disclosure.disclosure_category,
        "known_ticker_codes": disclosure.ticker_codes,
    }
    input_payload = {
        **full_payload,
        "summary": _truncate(disclosure.summary, min(max_chars, 2_000)),
        "body_text": _truncate(disclosure.body_text, max_chars),
    }
    return SourceDocument(
        source_type="kap",
        source_id=disclosure.disclosure_index,
        published_at=disclosure.published_at,
        content_hash=content_hash(full_payload),
        payload=input_payload,
    )


def build_user_content(document: SourceDocument, *, tier1_result: dict | None = None) -> str:
    parts = ["<SOURCE_DOCUMENT>", _prompt_json(document.payload), "</SOURCE_DOCUMENT>"]
    if tier1_result is not None:
        parts.extend(["<TIER1_RESULT>", _prompt_json(tier1_result), "</TIER1_RESULT>"])
    return "\n".join(parts)


def batch_document_id(document: SourceDocument) -> str:
    return f"{document.source_type}:{document.source_id}:{document.content_hash[:16]}"


def build_batch_user_content(documents: list[SourceDocument]) -> str:
    payload = [
        {
            "document_id": batch_document_id(document),
            "source_document": document.payload,
        }
        for document in documents
    ]
    return "\n".join(
        [
            "<BATCH_DOCUMENTS>",
            _prompt_json(payload),
            "</BATCH_DOCUMENTS>",
            (
                "Her belge icin document_id degerini degistirmeden, ayni sirada ve "
                "tam bir sonuc dondur."
            ),
        ]
    )


def _allocate_tokens(total: int | None, count: int) -> list[int | None]:
    """Grup tokenlarini toplami koruyacak bicimde kayitlara esit dagit."""
    if total is None:
        return [None] * count
    quotient, remainder = divmod(total, count)
    return [quotient + (1 if index < remainder else 0) for index in range(count)]


def _is_retryable_gemini_error(exc: Exception) -> bool:
    """Yalniz gecici ag/saglayici ve yarim JSON akislarini yeniden dene."""
    if isinstance(exc, ValidationError):
        return any(item["type"] == "json_invalid" for item in exc.errors())
    if isinstance(exc, (ConnectionError, TimeoutError, httpx.TransportError)):
        return True
    code = getattr(exc, "code", None)
    if isinstance(code, int) and (code in {408, 425} or code >= 500):
        return True
    message = str(exc).lower().lstrip()
    if message.startswith("<!doctype html>") and "error 403" in message:
        return True
    return any(
        marker in message
        for marker in (
            "high demand",
            "connection error",
            "connection reset",
            "temporarily unavailable",
            "timed out",
            "timeout",
        )
    )


def _friendly_gemini_error(exc: Exception) -> str:
    message = str(exc).strip()
    lowered = message.lower()
    if lowered.startswith("<!doctype html>") and "error 403" in lowered:
        return "Gemini API gecici olarak HTTP 403 HTML yaniti dondurdu"
    if isinstance(exc, ValidationError) and any(
        item["type"] == "json_invalid" for item in exc.errors()
    ):
        return "Gemini yapilandirilmis yaniti eksik veya gecersiz JSON dondurdu"
    if "connection error" in lowered or "timed out" in lowered or "timeout" in lowered:
        return "Gemini API baglantisi zaman asimina ugradi veya kesildi"
    return message[:4000]


def _is_batch_response_error(exc: Exception) -> bool:
    return isinstance(exc, ValidationError) or (
        isinstance(exc, ValueError)
        and str(exc).startswith("Gemini batch document_id sirasi/girdileriyle eslesmedi")
    )


def _prioritize_documents(
    documents: dict[tuple[str, int, str], SourceDocument],
    retry_keys: set[tuple[str, int, str]],
) -> list[SourceDocument]:
    """Basarisiz kayitlari yeni backlog tarafindan ac birakmadan basa al."""

    def newest_first(item: SourceDocument) -> tuple[datetime, str, int]:
        return item.published_at, item.source_type, item.source_id

    retries = sorted(
        (document for key, document in documents.items() if key in retry_keys),
        key=newest_first,
        reverse=True,
    )
    remaining = sorted(
        (document for key, document in documents.items() if key not in retry_keys),
        key=newest_first,
        reverse=True,
    )
    return [*retries, *remaining]


class GeminiGateway:
    """Google Gen AI SDK'nin testlerde kolayca degistirilebilen ince adaptoru."""

    _max_attempts = 3
    _retry_delays = (2.0, 8.0)

    def __init__(self, api_key: str, *, api_mode: str = "interactions") -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY bos")
        if api_mode not in {"interactions", "generate_content"}:
            raise ValueError(f"Desteklenmeyen Gemini API modu: {api_mode!r}")
        from google import genai

        self._client = genai.Client(api_key=api_key).aio
        self._api_mode = api_mode

    async def aclose(self) -> None:
        await self._client.aclose()

    async def generate(
        self,
        *,
        model: str,
        system_instruction: str,
        user_content: str,
        response_model: type[BaseModel],
        thinking_level: str,
        max_output_tokens: int,
    ) -> GatewayResponse:
        for attempt in range(1, self._max_attempts + 1):
            try:
                if self._api_mode == "interactions":
                    return await self._generate_interaction(
                        model=model,
                        system_instruction=system_instruction,
                        user_content=user_content,
                        response_model=response_model,
                        thinking_level=thinking_level,
                        max_output_tokens=max_output_tokens,
                    )
                return await self._generate_content(
                    model=model,
                    system_instruction=system_instruction,
                    user_content=user_content,
                    response_model=response_model,
                    thinking_level=thinking_level,
                    max_output_tokens=max_output_tokens,
                )
            except Exception as exc:
                if attempt >= self._max_attempts or not _is_retryable_gemini_error(exc):
                    raise
                delay = self._retry_delays[min(attempt - 1, len(self._retry_delays) - 1)]
                logger.warning(
                    "gemini_request_retry",
                    api_mode=self._api_mode,
                    model=model,
                    attempt=attempt,
                    retry_in_seconds=delay,
                    error=_friendly_gemini_error(exc),
                )
                await asyncio.sleep(delay)
        raise RuntimeError("Gemini retry dongusu beklenmedik bicimde sonlandi")

    async def _generate_interaction(
        self,
        *,
        model: str,
        system_instruction: str,
        user_content: str,
        response_model: type[BaseModel],
        thinking_level: str,
        max_output_tokens: int,
    ) -> GatewayResponse:
        stream = await self._client.interactions.create(
            model=model,
            input=user_content,
            system_instruction=system_instruction,
            generation_config={
                "thinking_level": thinking_level,
                "max_output_tokens": max_output_tokens,
            },
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": response_model.model_json_schema(),
            },
            store=False,
            stream=True,
        )
        text_parts: list[str] = []
        usage = None
        async for event in stream:
            event_type = getattr(event, "event_type", None)
            if event_type == "step.delta":
                delta = getattr(event, "delta", None)
                if getattr(delta, "type", None) == "text":
                    text_parts.append(delta.text)
            elif event_type == "interaction.completed":
                usage = getattr(getattr(event, "interaction", None), "usage", None)
            elif event_type == "error":
                raise RuntimeError(f"Gemini interaction stream hatasi: {event.error}")

        raw_text = "".join(text_parts)
        if not raw_text:
            raise RuntimeError("Gemini interaction stream metin cikisi dondurmedi")
        parsed = response_model.model_validate_json(raw_text)
        output_tokens = (getattr(usage, "total_output_tokens", None) or 0) + (
            getattr(usage, "total_thought_tokens", None) or 0
        )
        return GatewayResponse(
            data=parsed.model_dump(mode="json"),
            raw_text=raw_text,
            input_tokens=getattr(usage, "total_input_tokens", None),
            output_tokens=output_tokens or None,
            total_tokens=getattr(usage, "total_tokens", None),
        )

    async def _generate_content(
        self,
        *,
        model: str,
        system_instruction: str,
        user_content: str,
        response_model: type[BaseModel],
        thinking_level: str,
        max_output_tokens: int,
    ) -> GatewayResponse:
        from google.genai import types

        response = await self._client.models.generate_content(
            model=model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_json_schema=response_model.model_json_schema(),
                thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
                max_output_tokens=max_output_tokens,
            ),
        )
        raw_text = response.text or ""
        parsed = response_model.model_validate_json(raw_text)
        usage = response.usage_metadata
        output_tokens = (getattr(usage, "candidates_token_count", None) or 0) + (
            getattr(usage, "thoughts_token_count", None) or 0
        )
        return GatewayResponse(
            data=parsed.model_dump(mode="json"),
            raw_text=raw_text,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=output_tokens or None,
            total_tokens=getattr(usage, "total_token_count", None),
        )


class LlmEvaluationService:
    def __init__(
        self,
        session: AsyncSession,
        gateway: LlmGateway,
        *,
        settings: Settings | None = None,
        prompts: PromptBundle | None = None,
    ) -> None:
        self._session = session
        self._gateway = gateway
        self._settings = settings or get_settings()
        self._prompts = prompts or load_prompts()

    async def _known_tickers(self) -> set[str]:
        result = await self._session.scalars(
            select(Instrument.ticker).where(Instrument.is_active.is_(True))
        )
        return set(result.all())

    async def _daily_usage(self) -> tuple[int, int]:
        midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        row = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(LlmEvaluation.input_tokens), 0),
                    func.coalesce(func.sum(LlmEvaluation.output_tokens), 0),
                ).where(
                    LlmEvaluation.status == "succeeded",
                    LlmEvaluation.completed_at >= midnight,
                )
            )
        ).one()
        return int(row[0]), int(row[1])

    def _budget_available(self, input_tokens: int, output_tokens: int) -> bool:
        return (
            input_tokens < self._settings.llm_daily_input_token_limit
            and output_tokens < self._settings.llm_daily_output_token_limit
        )

    async def _tier1_documents(self) -> list[SourceDocument]:
        scan_limit = max(self._settings.llm_batch_size * 5, 100)
        model = self._settings.gemini_model_tier1
        api_mode = self._settings.gemini_api_mode
        news_evaluated = (
            select(LlmEvaluation.id)
            .where(
                LlmEvaluation.source_type == "news",
                LlmEvaluation.source_id == NewsArticle.id,
                LlmEvaluation.tier == 1,
                LlmEvaluation.prompt_version == PROMPT_VERSION,
                LlmEvaluation.model == model,
                LlmEvaluation.api_mode == api_mode,
            )
            .exists()
        )
        kap_evaluated = (
            select(LlmEvaluation.id)
            .where(
                LlmEvaluation.source_type == "kap",
                LlmEvaluation.source_id == KapDisclosure.disclosure_index,
                LlmEvaluation.tier == 1,
                LlmEvaluation.prompt_version == PROMPT_VERSION,
                LlmEvaluation.model == model,
                LlmEvaluation.api_mode == api_mode,
            )
            .exists()
        )

        recent_news = (
            await self._session.scalars(
                select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(scan_limit)
            )
        ).all()
        backlog_news = (
            await self._session.scalars(
                select(NewsArticle)
                .where(~news_evaluated)
                .order_by(NewsArticle.published_at.desc())
                .limit(scan_limit)
            )
        ).all()
        recent_disclosures = (
            await self._session.scalars(
                select(KapDisclosure).order_by(KapDisclosure.published_at.desc()).limit(scan_limit)
            )
        ).unique().all()
        backlog_disclosures = (
            await self._session.scalars(
                select(KapDisclosure)
                .where(~kap_evaluated)
                .order_by(KapDisclosure.published_at.desc())
                .limit(scan_limit)
            )
        ).unique().all()

        stale_before = datetime.now(UTC) - timedelta(minutes=30)
        retry_records = (
            await self._session.scalars(
                select(LlmEvaluation)
                .where(
                    LlmEvaluation.tier == 1,
                    LlmEvaluation.prompt_version == PROMPT_VERSION,
                    LlmEvaluation.model == model,
                    LlmEvaluation.api_mode == api_mode,
                    LlmEvaluation.attempt_count < self._settings.llm_max_attempts,
                    or_(
                        LlmEvaluation.status == "failed",
                        (LlmEvaluation.status == "running")
                        & (LlmEvaluation.started_at < stale_before),
                    ),
                )
                .order_by(LlmEvaluation.completed_at.desc().nullslast())
                .limit(scan_limit)
            )
        ).all()

        documents: dict[tuple[str, int, str], SourceDocument] = {}
        for row in [*recent_news, *backlog_news]:
            document = document_from_news(row, max_chars=self._settings.llm_max_source_chars)
            documents[(document.source_type, document.source_id, document.content_hash)] = document
        for row in [*recent_disclosures, *backlog_disclosures]:
            document = document_from_kap(row, max_chars=self._settings.llm_max_source_chars)
            documents[(document.source_type, document.source_id, document.content_hash)] = document
        retry_keys: set[tuple[str, int, str]] = set()
        for record in retry_records:
            document = await self._load_document(record.source_type, record.source_id)
            if document is not None and document.content_hash == record.content_hash:
                key = (document.source_type, document.source_id, document.content_hash)
                documents[key] = document
                retry_keys.add(key)

        return _prioritize_documents(documents, retry_keys)

    async def _load_document(self, source_type: str, source_id: int) -> SourceDocument | None:
        if source_type == "news":
            article = await self._session.get(NewsArticle, source_id)
            return (
                document_from_news(article, max_chars=self._settings.llm_max_source_chars)
                if article
                else None
            )
        disclosure = await self._session.get(KapDisclosure, source_id)
        return (
            document_from_kap(disclosure, max_chars=self._settings.llm_max_source_chars)
            if disclosure
            else None
        )

    async def _tier2_parents(self) -> Sequence[LlmEvaluation]:
        child = aliased(LlmEvaluation)
        api_mode = self._settings.gemini_api_mode
        tier2_model = self._settings.gemini_model_tier2
        child_exists = (
            select(child.id)
            .where(
                child.parent_evaluation_key == LlmEvaluation.evaluation_key,
                child.api_mode == api_mode,
                child.model == tier2_model,
            )
            .exists()
        )
        stale_before = datetime.now(UTC) - timedelta(minutes=30)
        retryable_child_exists = (
            select(child.id)
            .where(
                child.parent_evaluation_key == LlmEvaluation.evaluation_key,
                child.api_mode == api_mode,
                child.model == tier2_model,
                child.attempt_count < self._settings.llm_max_attempts,
                or_(
                    child.status == "failed",
                    (child.status == "running") & (child.started_at < stale_before),
                ),
            )
            .exists()
        )
        return (
            await self._session.scalars(
                select(LlmEvaluation)
                .where(
                    LlmEvaluation.tier == 1,
                    LlmEvaluation.api_mode == api_mode,
                    LlmEvaluation.model == self._settings.gemini_model_tier1,
                    LlmEvaluation.status == "succeeded",
                    LlmEvaluation.requires_tier2.is_(True),
                    or_(~child_exists, retryable_child_exists),
                )
                .order_by(LlmEvaluation.impact_score.desc(), LlmEvaluation.completed_at.desc())
                .limit(max(self._settings.llm_batch_size * 10, 100))
            )
        ).all()

    async def _existing(self, key: str) -> LlmEvaluation | None:
        return await self._session.scalar(
            select(LlmEvaluation).where(LlmEvaluation.evaluation_key == key)
        )

    @staticmethod
    def _can_attempt(record: LlmEvaluation | None, max_attempts: int) -> bool:
        if record is None:
            return True
        if record.status == "succeeded" or record.attempt_count >= max_attempts:
            return False
        if record.status == "running":
            stale_before = datetime.now(UTC) - timedelta(minutes=30)
            started_at = record.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            return started_at < stale_before
        return True

    async def _start_record(
        self,
        document: SourceDocument,
        *,
        key: str,
        tier: int,
        model: str,
        input_document: dict,
        parent_key: str | None,
    ) -> LlmEvaluation | None:
        record = await self._existing(key)
        if not self._can_attempt(record, self._settings.llm_max_attempts):
            return None
        now = datetime.now(UTC)
        if record is None:
            record = LlmEvaluation(
                evaluation_key=key,
                parent_evaluation_key=parent_key,
                source_type=document.source_type,
                source_id=document.source_id,
                content_hash=document.content_hash,
                prompt_version=PROMPT_VERSION,
                tier=tier,
                provider="google",
                api_mode=self._settings.gemini_api_mode,
                model=model,
                status="running",
                attempt_count=1,
                input_document=input_document,
                ticker_codes=[],
                requires_tier2=False,
                started_at=now,
            )
            self._session.add(record)
        else:
            record.status = "running"
            record.attempt_count += 1
            record.input_document = input_document
            record.started_at = now
            record.completed_at = None
            record.error_text = None
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            return None
        return record

    def _complete_record(
        self,
        record: LlmEvaluation,
        validated: dict,
        *,
        tier: int,
        known_tickers: set[str],
        raw_response: str,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        latency_ms: int,
        batch_metadata: dict | None = None,
    ) -> None:
        validated = dict(validated)
        validated["ticker_codes"] = sorted(
            set(validated.get("ticker_codes", [])) & known_tickers
        )
        requires_tier2 = bool(
            tier == 1
            and validated.get("requires_deep_analysis")
            and validated["relevant"]
            and validated["relevance_score"] >= 60
            and validated["impact_score"] >= self._settings.llm_tier2_min_impact
            and validated["ticker_codes"]
        )
        if batch_metadata:
            validated["_batch"] = batch_metadata

        record.status = "succeeded"
        record.ticker_codes = validated["ticker_codes"]
        record.relevance_score = validated["relevance_score"]
        record.sentiment_score = validated["sentiment_score"]
        record.impact_score = validated["impact_score"]
        record.confidence = validated["confidence"]
        record.event_type = validated["event_type"]
        record.time_horizon = validated["time_horizon"]
        record.summary = validated["summary"]
        record.rationale = validated["rationale"]
        record.requires_tier2 = requires_tier2
        record.result = validated
        record.raw_response = raw_response
        record.input_tokens = input_tokens
        record.output_tokens = output_tokens
        record.total_tokens = total_tokens
        record.latency_ms = latency_ms
        record.completed_at = datetime.now(UTC)
        record.error_text = None

    async def _evaluate_tier1_batch(
        self,
        documents: list[SourceDocument],
        *,
        known_tickers: set[str],
    ) -> BatchEvaluationOutcome:
        model = self._settings.gemini_model_tier1
        prepared: list[tuple[SourceDocument, str, LlmEvaluation]] = []
        skipped = 0
        for document in documents:
            key = evaluation_key(
                document,
                tier=1,
                model=model,
                api_mode=self._settings.gemini_api_mode,
            )
            record = await self._start_record(
                document,
                key=key,
                tier=1,
                model=model,
                input_document={"source_document": document.payload},
                parent_key=None,
            )
            if record is None:
                skipped += 1
            else:
                prepared.append((document, key, record))
        if not prepared:
            return BatchEvaluationOutcome(0, 0, 0, skipped)

        started = time.monotonic()
        try:
            active_documents = [item[0] for item in prepared]
            response = await self._gateway.generate(
                model=model,
                system_instruction=self._prompts.tier1_system,
                user_content=build_batch_user_content(active_documents),
                response_model=LlmTier1BatchResult,
                thinking_level="low",
                max_output_tokens=min(8_192, max(2_400, len(prepared) * 450)),
            )
            batch = LlmTier1BatchResult.model_validate(response.data)
            expected_ids = [batch_document_id(document) for document in active_documents]
            actual_ids = [item.document_id for item in batch.results]
            if actual_ids != expected_ids:
                raise ValueError(
                    "Gemini batch document_id sirasi/girdileriyle eslesmedi: "
                    f"expected={expected_ids!r}, actual={actual_ids!r}"
                )

            latency_ms = round((time.monotonic() - started) * 1000)
            input_allocations = _allocate_tokens(response.input_tokens, len(prepared))
            output_allocations = _allocate_tokens(response.output_tokens, len(prepared))
            total_allocations = _allocate_tokens(response.total_tokens, len(prepared))
            for index, ((_, _, record), item) in enumerate(zip(prepared, batch.results, strict=True)):
                validated = item.model_dump(mode="json", exclude={"document_id"})
                self._complete_record(
                    record,
                    validated,
                    tier=1,
                    known_tickers=known_tickers,
                    raw_response=_stable_json(item.model_dump(mode="json")),
                    input_tokens=input_allocations[index],
                    output_tokens=output_allocations[index],
                    total_tokens=total_allocations[index],
                    latency_ms=latency_ms,
                    batch_metadata={
                        "size": len(prepared),
                        "position": index + 1,
                        "usage_allocation": "even",
                    },
                )
            await self._session.commit()
            return BatchEvaluationOutcome(
                attempted=len(prepared),
                succeeded=len(prepared),
                failed=0,
                skipped=skipped,
                input_tokens=response.input_tokens or 0,
                output_tokens=response.output_tokens or 0,
            )
        except Exception as exc:  # noqa: BLE001 - grup hatasi batch'i durdurmasin
            await self._session.rollback()
            if len(prepared) > 1 and _is_batch_response_error(exc):
                succeeded = failed = input_tokens = output_tokens = 0
                for document, key, _ in prepared:
                    status, response = await self._evaluate_running_tier1(
                        document,
                        key=key,
                        known_tickers=known_tickers,
                    )
                    if status == "succeeded":
                        succeeded += 1
                    else:
                        failed += 1
                    if response:
                        input_tokens += response.input_tokens or 0
                        output_tokens += response.output_tokens or 0
                return BatchEvaluationOutcome(
                    attempted=len(prepared),
                    succeeded=succeeded,
                    failed=failed,
                    skipped=skipped,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            latency_ms = round((time.monotonic() - started) * 1000)
            for _, key, _ in prepared:
                record = await self._existing(key)
                if record is not None:
                    record.status = "failed"
                    record.error_text = _friendly_gemini_error(exc)
                    record.latency_ms = latency_ms
                    record.completed_at = datetime.now(UTC)
            await self._session.commit()
            return BatchEvaluationOutcome(
                attempted=len(prepared),
                succeeded=0,
                failed=len(prepared),
                skipped=skipped,
            )

    async def _evaluate_running_tier1(
        self,
        document: SourceDocument,
        *,
        key: str,
        known_tickers: set[str],
    ) -> tuple[str, GatewayResponse | None]:
        """Basarisiz grup semasindaki tek kaydi yeni attempt acmadan izole et."""
        started = time.monotonic()
        try:
            response = await self._gateway.generate(
                model=self._settings.gemini_model_tier1,
                system_instruction=self._prompts.tier1_system,
                user_content=build_user_content(document),
                response_model=LlmTier1Result,
                thinking_level="low",
                max_output_tokens=2_400,
            )
            validated = LlmTier1Result.model_validate(response.data).model_dump(mode="json")
            record = await self._existing(key)
            if record is None:
                return "failed", None
            self._complete_record(
                record,
                validated,
                tier=1,
                known_tickers=known_tickers,
                raw_response=response.raw_text,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                latency_ms=round((time.monotonic() - started) * 1000),
                batch_metadata={"size": 1, "position": 1, "fallback": "group_isolation"},
            )
            await self._session.commit()
            return "succeeded", response
        except Exception as exc:  # noqa: BLE001 - tek oge digerlerini etkilemesin
            await self._session.rollback()
            record = await self._existing(key)
            if record is not None:
                record.status = "failed"
                record.error_text = _friendly_gemini_error(exc)
                record.latency_ms = round((time.monotonic() - started) * 1000)
                record.completed_at = datetime.now(UTC)
                await self._session.commit()
            return "failed", None

    async def _evaluate(
        self,
        document: SourceDocument,
        *,
        tier: int,
        known_tickers: set[str],
        parent: LlmEvaluation | None = None,
    ) -> tuple[str, GatewayResponse | None]:
        model = (
            self._settings.gemini_model_tier1
            if tier == 1
            else self._settings.gemini_model_tier2
        )
        parent_key = parent.evaluation_key if parent else None
        key = evaluation_key(
            document,
            tier=tier,
            model=model,
            api_mode=self._settings.gemini_api_mode,
            parent_key=parent_key,
        )
        tier1_result = parent.result if parent else None
        input_document = {"source_document": document.payload}
        if tier1_result is not None:
            input_document["tier1_result"] = tier1_result
        record = await self._start_record(
            document,
            key=key,
            tier=tier,
            model=model,
            input_document=input_document,
            parent_key=parent_key,
        )
        if record is None:
            return "skipped", None

        started = time.monotonic()
        try:
            response_model: type[BaseModel] = LlmTier1Result if tier == 1 else LlmTier2Result
            response = await self._gateway.generate(
                model=model,
                system_instruction=(
                    self._prompts.tier1_system if tier == 1 else self._prompts.tier2_system
                ),
                user_content=build_user_content(document, tier1_result=tier1_result),
                response_model=response_model,
                thinking_level="low" if tier == 1 else "medium",
                max_output_tokens=2_400 if tier == 1 else 4_096,
            )
            validated = response_model.model_validate(response.data).model_dump(mode="json")
            self._complete_record(
                record,
                validated,
                tier=tier,
                known_tickers=known_tickers,
                raw_response=response.raw_text,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                latency_ms=round((time.monotonic() - started) * 1000),
            )
            await self._session.commit()
            return "succeeded", response
        except Exception as exc:  # noqa: BLE001 - tek model hatasi batch'i durdurmasin
            await self._session.rollback()
            record = await self._existing(key)
            if record is not None:
                record.status = "failed"
                record.error_text = _friendly_gemini_error(exc)
                record.latency_ms = round((time.monotonic() - started) * 1000)
                record.completed_at = datetime.now(UTC)
                await self._session.commit()
            return "failed", None

    async def run(self) -> dict:
        known_tickers = await self._known_tickers()
        input_tokens, output_tokens = await self._daily_usage()
        result = {
            "tier1_succeeded": 0,
            "tier1_failed": 0,
            "tier2_succeeded": 0,
            "tier2_failed": 0,
            "skipped": 0,
            "budget_exhausted": False,
        }

        tier1_attempted = 0
        tier1_documents = await self._tier1_documents()
        tier1_cursor = 0
        group_size = max(1, min(self._settings.llm_tier1_group_size, 20))
        while tier1_cursor < len(tier1_documents):
            if not self._budget_available(input_tokens, output_tokens):
                result["budget_exhausted"] = True
                break
            remaining_capacity = self._settings.llm_batch_size - tier1_attempted
            if remaining_capacity <= 0:
                break
            current_group_size = min(group_size, remaining_capacity)
            documents = tier1_documents[tier1_cursor : tier1_cursor + current_group_size]
            tier1_cursor += len(documents)
            outcome = await self._evaluate_tier1_batch(
                documents,
                known_tickers=known_tickers,
            )
            tier1_attempted += outcome.attempted
            result["tier1_succeeded"] += outcome.succeeded
            result["tier1_failed"] += outcome.failed
            result["skipped"] += outcome.skipped
            input_tokens += outcome.input_tokens
            output_tokens += outcome.output_tokens

        tier2_attempted = 0
        tier2_batch_size = max(1, self._settings.llm_batch_size // 4)
        if not result["budget_exhausted"]:
            for parent in await self._tier2_parents():
                if tier2_attempted >= tier2_batch_size:
                    break
                if not self._budget_available(input_tokens, output_tokens):
                    result["budget_exhausted"] = True
                    break
                document = await self._load_document(parent.source_type, parent.source_id)
                if document is None or document.content_hash != parent.content_hash:
                    result["skipped"] += 1
                    continue
                status, response = await self._evaluate(
                    document,
                    tier=2,
                    known_tickers=known_tickers,
                    parent=parent,
                )
                if status == "skipped":
                    result["skipped"] += 1
                    continue
                tier2_attempted += 1
                result[f"tier2_{status}"] += 1
                if response:
                    input_tokens += response.input_tokens or 0
                    output_tokens += response.output_tokens or 0

        result["daily_input_tokens"] = input_tokens
        result["daily_output_tokens"] = output_tokens
        return result


async def run_llm_evaluations(session: AsyncSession, *, settings: Settings | None = None) -> dict:
    active_settings = settings or await resolve_settings()
    if not active_settings.llm_enabled:
        return {"enabled": False, "reason": "LLM_ENABLED=false"}
    if not active_settings.gemini_api_key:
        raise RuntimeError("LLM_ENABLED=true fakat GEMINI_API_KEY bos")

    gateway = GeminiGateway(
        active_settings.gemini_api_key,
        api_mode=active_settings.gemini_api_mode,
    )
    try:
        result = await LlmEvaluationService(
            session,
            gateway,
            settings=active_settings,
        ).run()
        return {"enabled": True, **result}
    finally:
        await gateway.aclose()
