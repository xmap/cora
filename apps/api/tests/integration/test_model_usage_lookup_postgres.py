"""Integration tests for `PostgresModelUsageLookup` over `entries_decision_inferences`.

Seeds inference rows directly through `PostgresInferenceStore` (the
same write path production uses) and verifies the three match arms
(request_model equality, response_model equality, response_model dated
snapshot via LIKE), the provider filter, and the DISTINCT ON collapse
to one newest row per Decision.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.decision.adapters import PostgresModelUsageLookup
from cora.decision.aggregates.decision import Inference
from cora.decision.aggregates.decision.entries import PostgresInferenceStore

_PROVIDER = "anthropic"
_MODEL = "claude-sonnet-4-5"

_T1 = datetime(2026, 7, 10, tzinfo=UTC)
_T2 = datetime(2026, 7, 11, tzinfo=UTC)
_T3 = datetime(2026, 7, 12, tzinfo=UTC)


def _row(
    *,
    decision_id: UUID,
    occurred_at: datetime,
    provider_name: str = _PROVIDER,
    request_model: str = _MODEL,
    response_model: str | None = None,
    agent_id: str | None = None,
) -> Inference:
    return Inference(
        event_id=uuid4(),
        decision_id=decision_id,
        logbook_id=uuid4(),
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=occurred_at,
        duration=None,
        operation_name="chat",
        provider_name=provider_name,
        request_model=request_model,
        response_id=None,
        response_model=response_model,
        request_temperature=None,
        request_top_p=None,
        request_max_tokens=None,
        output_type=None,
        finish_reasons=(),
        input_tokens=100,
        output_tokens=50,
        cost_usd=None,
        agent_id=agent_id,
        agent_name=None,
        agent_description=None,
        conversation_id=None,
        tool_name=None,
        tool_call_id=None,
        tool_type=None,
        messages=None,
    )


@pytest.mark.integration
async def test_finds_decisions_by_request_model_and_dated_snapshot_response(
    db_pool: asyncpg.Pool,
) -> None:
    """A row matches on request_model equality OR on a response_model
    that is the alias's dated snapshot (the LIKE arm); rows for other
    model identities are excluded; results come back newest first."""
    store = PostgresInferenceStore(db_pool)
    request_match_id = uuid4()
    snapshot_match_id = uuid4()
    other_model_id = uuid4()
    await store.append(
        [
            _row(
                decision_id=request_match_id,
                occurred_at=_T1,
                agent_id="run-debriefer",
            ),
            # Alias resolved onto a dated snapshot: the request named a
            # DIFFERENT model, only response_model ties it to the alias.
            _row(
                decision_id=snapshot_match_id,
                occurred_at=_T2,
                request_model="claude-haiku-4-5",
                response_model=f"{_MODEL}-20250929",
            ),
            _row(
                decision_id=other_model_id,
                occurred_at=_T2,
                request_model="claude-haiku-4-5",
                response_model="claude-haiku-4-5-20251001",
            ),
        ]
    )

    results = await PostgresModelUsageLookup(db_pool).find_decisions_touching_model(
        provider=_PROVIDER,
        model=_MODEL,
    )

    assert [r.decision_id for r in results] == [snapshot_match_id, request_match_id]
    assert results[0].response_model == f"{_MODEL}-20250929"
    assert results[1].request_model == _MODEL
    assert results[1].agent_id == "run-debriefer"


@pytest.mark.integration
async def test_sibling_minor_versions_are_excluded_from_the_snapshot_arm(
    db_pool: asyncpg.Pool,
) -> None:
    """The snapshot arm matches exactly eight suffix characters (the
    YYYYMMDD date), so sibling minor versions of the queried entry
    (`-5`, `-59`, `-5x` after `claude-sonnet-4`) never count as a
    touch, while the entry's own dated snapshot does."""
    store = PostgresInferenceStore(db_pool)
    own_snapshot_id = uuid4()
    await store.append(
        [
            _row(
                decision_id=own_snapshot_id,
                occurred_at=_T1,
                request_model="claude-haiku-4-5",
                response_model="claude-sonnet-4-20250514",
            ),
            _row(
                decision_id=uuid4(),
                occurred_at=_T1,
                request_model="claude-haiku-4-5",
                response_model="claude-sonnet-4-5",
            ),
            _row(
                decision_id=uuid4(),
                occurred_at=_T1,
                request_model="claude-haiku-4-5",
                response_model="claude-sonnet-4-59",
            ),
            _row(
                decision_id=uuid4(),
                occurred_at=_T1,
                request_model="claude-haiku-4-5",
                response_model="claude-sonnet-4-5x",
            ),
        ]
    )

    results = await PostgresModelUsageLookup(db_pool).find_decisions_touching_model(
        provider=_PROVIDER,
        model="claude-sonnet-4",
    )

    assert [r.decision_id for r in results] == [own_snapshot_id]


@pytest.mark.integration
async def test_snapshot_matching_never_bleeds_between_sibling_models(
    db_pool: asyncpg.Pool,
) -> None:
    """Both directions of the sibling seam: entry claude-sonnet-4 is
    not touched by claude-sonnet-4-5 calls or its dated snapshot, and
    entry claude-sonnet-4-5 is not touched by claude-sonnet-4's own
    dated snapshot; each entry matches only its own snapshot."""
    store = PostgresInferenceStore(db_pool)
    sonnet_4_snapshot_id = uuid4()
    sonnet_4_5_snapshot_id = uuid4()
    await store.append(
        [
            _row(
                decision_id=sonnet_4_snapshot_id,
                occurred_at=_T1,
                request_model="claude-haiku-4-5",
                response_model="claude-sonnet-4-20250514",
            ),
            _row(
                decision_id=sonnet_4_5_snapshot_id,
                occurred_at=_T2,
                request_model="claude-haiku-4-5",
                response_model=f"{_MODEL}-20250929",
            ),
        ]
    )
    lookup = PostgresModelUsageLookup(db_pool)

    sonnet_4_results = await lookup.find_decisions_touching_model(
        provider=_PROVIDER,
        model="claude-sonnet-4",
    )
    sonnet_4_5_results = await lookup.find_decisions_touching_model(
        provider=_PROVIDER,
        model=_MODEL,
    )

    assert [r.decision_id for r in sonnet_4_results] == [sonnet_4_snapshot_id]
    assert [r.decision_id for r in sonnet_4_5_results] == [sonnet_4_5_snapshot_id]


@pytest.mark.integration
async def test_rows_from_other_providers_are_excluded(db_pool: asyncpg.Pool) -> None:
    """The same model string under a different provider_name is a
    different identity and never counts as a touch."""
    store = PostgresInferenceStore(db_pool)
    matching_id = uuid4()
    await store.append(
        [
            _row(decision_id=matching_id, occurred_at=_T1),
            _row(decision_id=uuid4(), occurred_at=_T1, provider_name="openai"),
        ]
    )

    results = await PostgresModelUsageLookup(db_pool).find_decisions_touching_model(
        provider=_PROVIDER,
        model=_MODEL,
    )

    assert [r.decision_id for r in results] == [matching_id]


@pytest.mark.integration
async def test_two_rows_for_one_decision_are_collapsed_to_the_newest(
    db_pool: asyncpg.Pool,
) -> None:
    """DISTINCT ON keeps exactly one row per Decision, and it is the
    newest touching call (its occurred_at / agent_id win)."""
    store = PostgresInferenceStore(db_pool)
    decision_id = uuid4()
    await store.append(
        [
            _row(decision_id=decision_id, occurred_at=_T1, agent_id="older-call"),
            _row(
                decision_id=decision_id,
                occurred_at=_T3,
                response_model=f"{_MODEL}-20250929",
                agent_id="newer-call",
            ),
        ]
    )

    results = await PostgresModelUsageLookup(db_pool).find_decisions_touching_model(
        provider=_PROVIDER,
        model=_MODEL,
    )

    assert len(results) == 1
    assert results[0].decision_id == decision_id
    assert results[0].occurred_at == _T3
    assert results[0].agent_id == "newer-call"
    assert results[0].response_model == f"{_MODEL}-20250929"


@pytest.mark.integration
async def test_model_with_no_touching_rows_returns_empty_tuple(db_pool: asyncpg.Pool) -> None:
    results = await PostgresModelUsageLookup(db_pool).find_decisions_touching_model(
        provider=_PROVIDER,
        model="claude-opus-4-1",
    )

    assert results == ()
