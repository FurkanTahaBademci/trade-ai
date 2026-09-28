# Production review — 2026-09-28

Target: https://trade.furkantahabademci.com.tr/ (remote production only).
Observation around 19:18 Europe/Istanbul: overview, system, THYAO and news
returned HTTP 200. Collector status was 11/11 healthy. The AI report showed
1,073 successes and 163 failures today, 6,622 unresolved failures, 15 pending
documents, and five records running longer than 30 minutes. These are point-in-time
counts, not permanent system properties.

The latest 30 evaluations contained 26 failures and four running records. The
failures explicitly reported a Gemini Free Tier daily request quota (500/day).
This is a provider limit, independent of the application's token budget.

## Changes

- Detect provider quota errors and stop further batches/Tier 2 calls in the current
  worker run; consult persisted failures before subsequent runs and after restart.
- Daily quota backoff lasts until midnight America/Los_Angeles, including DST.
  Short-term rate limits use the provider retry hint (60–3,600 seconds) or five
  minutes when unspecified. Daily exhaustion takes precedence over short retry hints.
- Quota errors remain audited but do not consume permanent per-document retries.
  Batch-isolation fallback also stops sending requests after a quota error.
- Pause lookup is scoped to currently configured models and API mode. A later
  successful evaluation clears the older failure. No DB migration is required.
- The system UI exposes provider pause and next retry time; unlimited application
  tokens are described as “Uygulama sınırı yok”, without implying unlimited provider
  access.
- Dates explicitly use Europe/Istanbul. The client-rendered news list uses absolute
  timestamps to avoid server/browser clock drift during hydration.

Google documents RPD reset at midnight Pacific time:
https://ai.google.dev/gemini-api/docs/rate-limits

## Verification and limits

Ruff, 203 backend tests, Alembic offline DDL, TypeScript, 43 web tests and Next
production build passed. New tests cover Pacific summer/winter/DST reset, transient
limits, persisted pause across sessions, expiry, model scoping, recovery, normal
batch failure, isolation fallback and skipping subsequent worker work.

At initial inspection the live site still served the pre-terminal UI despite
PR #2 being merged; its overview raised React hydration error 418. Nested anchors
were already removed by PR #2; this follow-up also makes timestamps deterministic.
These changes must be verified again after remote deployment. No live settings,
paid tier, provider credentials or evaluation records were modified during review.
Local TradeAI services remained stopped.

A provider pause currently conservatively pauses the whole evaluation pipeline
if either configured model is limited. Historical exhausted retries and stale
running records are retained, not silently deleted or reset. Access control for
public management actions remains an operational follow-up.
