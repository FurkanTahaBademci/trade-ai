from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from app.api.routers.evaluations import list_evaluations


def _db():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    return db


async def _sql(**overrides):
    db = _db()
    params = {
        "db": db,
        "source_type": None,
        "source_id": None,
        "ticker": None,
        "tier": None,
        "status": None,
        "before": None,
        "before_id": None,
        "limit": 12,
    }
    params.update(overrides)
    await list_evaluations(**params)
    compiled = db.execute.await_args.args[0].compile(dialect=postgresql.dialect())
    return str(compiled), compiled.params


async def test_min_impact_filters_by_impact_score():
    sql, params = await _sql(min_impact=20)
    assert "llm_evaluation.impact_score >=" in sql
    assert 20 in params.values()


async def test_min_impact_omitted_keeps_all_scores():
    sql, _ = await _sql()
    assert "impact_score >=" not in sql


async def test_min_impact_zero_still_applies():
    sql, params = await _sql(min_impact=0)
    assert "llm_evaluation.impact_score >=" in sql
    assert 0 in params.values()
