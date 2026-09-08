"""Iki katmanli Gemini degerlendirme servisi.

Tier 1 tum yeni haber/KAP girdilerini hizli modelle siniflandirir. Tier 2,
yalniz yuksek etkili ve aktif BIST ticker'i ile eslesen girdileri daha derin
modelle inceler. Her cagri oncesi DB'de `running` kaydi commit edilir; basari,
hata ve token kullanimi ayni kayitta denetlenebilir kalir.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import Settings, get_settings
from app.core.dynamic_settings import resolve_settings
from app.models import Instrument, KapDisclosure, LlmEvaluation, NewsArticle
from app.schemas.llm import LlmTier1Result, LlmTier2Result

if TYPE_CHECKING:
    from collections.abc import Sequence

PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md"
_PROMPT_SECTION_RE = re.compile(
    r"<!-- (?P<name>TIER[12]_SYSTEM) -->\s*(?P<body>.*?)\s*<!-- END_(?P=name) -->",
    re.DOTALL,
)


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


class GeminiGateway:
    """Google Gen AI SDK'nin testlerde kolayca degistirilebilen ince adaptoru."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY bos")
        from google import genai

        self._client = genai.Client(api_key=api_key).aio

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
        return GatewayResponse(
            data=parsed.model_dump(mode="json"),
            raw_text=raw_text,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
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
        news_evaluated = (
            select(LlmEvaluation.id)
            .where(
                LlmEvaluation.source_type == "news",
                LlmEvaluation.source_id == NewsArticle.id,
                LlmEvaluation.tier == 1,
                LlmEvaluation.prompt_version == PROMPT_VERSION,
                LlmEvaluation.model == model,
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
        for record in retry_records:
            document = await self._load_document(record.source_type, record.source_id)
            if document is not None and document.content_hash == record.content_hash:
                documents[(document.source_type, document.source_id, document.content_hash)] = document

        return sorted(
            documents.values(),
            key=lambda item: (item.published_at, item.source_type, item.source_id),
            reverse=True,
        )

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
        child_exists = (
            select(child.id)
            .where(child.parent_evaluation_key == LlmEvaluation.evaluation_key)
            .exists()
        )
        stale_before = datetime.now(UTC) - timedelta(minutes=30)
        retryable_child_exists = (
            select(child.id)
            .where(
                child.parent_evaluation_key == LlmEvaluation.evaluation_key,
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
        key = evaluation_key(document, tier=tier, model=model, parent_key=parent_key)
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
                max_output_tokens=1_200 if tier == 1 else 2_400,
            )
            validated = response_model.model_validate(response.data).model_dump(mode="json")
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
            record.raw_response = response.raw_text
            record.input_tokens = response.input_tokens
            record.output_tokens = response.output_tokens
            record.total_tokens = response.total_tokens
            record.latency_ms = round((time.monotonic() - started) * 1000)
            record.completed_at = datetime.now(UTC)
            record.error_text = None
            await self._session.commit()
            return "succeeded", response
        except Exception as exc:  # noqa: BLE001 - tek model hatasi batch'i durdurmasin
            await self._session.rollback()
            record = await self._existing(key)
            if record is not None:
                record.status = "failed"
                record.error_text = str(exc)[:4000]
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
        for document in await self._tier1_documents():
            if tier1_attempted >= self._settings.llm_batch_size:
                break
            if not self._budget_available(input_tokens, output_tokens):
                result["budget_exhausted"] = True
                break
            status, response = await self._evaluate(
                document,
                tier=1,
                known_tickers=known_tickers,
            )
            if status == "skipped":
                result["skipped"] += 1
                continue
            tier1_attempted += 1
            result[f"tier1_{status}"] += 1
            if response:
                input_tokens += response.input_tokens or 0
                output_tokens += response.output_tokens or 0

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

    gateway = GeminiGateway(active_settings.gemini_api_key)
    try:
        result = await LlmEvaluationService(
            session,
            gateway,
            settings=active_settings,
        ).run()
        return {"enabled": True, **result}
    finally:
        await gateway.aclose()
