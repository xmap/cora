"""End-to-end PG integration for `regenerate_run_debrief`.

Walks: seed RunDebriefer Agent + Actor -> start a Run -> invoke
`regenerate_run_debrief` handler -> verify a `DecisionRegistered`
lands on the Decision stream with `inputs["trigger"]="on-demand"`.
Uses `FakeLLM` (no Anthropic API key needed in CI).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingParameterType=false, reportUnknownParameterType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.features.regenerate_run_debrief import RegenerateRunDebrief, bind
from cora.agent.seed_run_debriefer_external import seed_run_debriefer_external_agent
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import FakeLLM, FakeLLMResponse
from cora.run.aggregates.run import RunStarted
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 17, 16, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000088001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000008800a")


_CANNED_OK = FakeLLMResponse(
    parsed={
        "choice": "DegradedCompletion",
        "confidence": 0.78,
        "reasoning": (
            "PG integration smoke test of on-demand debrief regeneration. Synopsis: "
            "a single-Plan Run was re-evaluated by operator request. "
            "What was supposed to happen: standard Plan execution. "
            "What actually happened: completed with mild deviation in "
            "effective_parameters. Why the difference: minor instrument "
            "drift; not blocking but worth noting."
        ),
    },
    stop_reason="tool_use",
    model_id="claude-haiku-4-5",
)


async def _seed_run(deps, run_id: UUID) -> None:
    started = RunStarted(
        run_id=run_id,
        name="PG Integration RegenerateDebrief Run",
        plan_id=UUID("01900000-0000-7000-8000-000000000401"),
        subject_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=run_event_type_name(started),
        payload=run_to_payload(started),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.integration
async def test_regenerate_run_debrief_handler_writes_decision_on_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    new_decision_id = uuid4()
    llm = FakeLLM(responses=[_CANNED_OK])
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[new_decision_id],
        llm=llm,
    )

    # Seed the RunDebriefer Agent + Actor (idempotent on PG).
    await seed_run_debriefer_external_agent(deps)

    # Seed a Run.
    run_id = uuid4()
    await _seed_run(deps, run_id)

    # Invoke the handler directly (skips the HTTP envelope; the
    # contract tests already cover the REST shape).
    handler = bind(deps)
    decision_id = await handler(
        RegenerateRunDebrief(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert decision_id == new_decision_id
    decision = await load_decision(deps.event_store, decision_id)
    assert decision is not None
    assert decision.choice.value == "DegradedCompletion"
    assert decision.context.value == "RunDebrief"
    assert decision.confidence == pytest.approx(0.78)
    # On-demand discriminator IS in inputs.
    assert decision.inputs is not None
    assert decision.inputs["trigger"] == "on-demand"
    assert decision.inputs["run_id"] == str(run_id)


@pytest.mark.integration
async def test_regenerate_run_debrief_chains_parent_via_inputs_lookup(
    db_pool: asyncpg.Pool,
) -> None:
    """Two-call sequence: first call lands a Decision; second call
    chains its parent_id to the first. The handler's parent-Run-
    scope guard validates the chain on PG."""
    parent_decision_id = uuid4()
    child_decision_id = uuid4()
    llm = FakeLLM(responses=[_CANNED_OK, _CANNED_OK])
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[parent_decision_id, child_decision_id],
        llm=llm,
    )
    await seed_run_debriefer_external_agent(deps)
    run_id = uuid4()
    await _seed_run(deps, run_id)
    handler = bind(deps)

    # First call.
    parent_id = await handler(
        RegenerateRunDebrief(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert parent_id == parent_decision_id

    # Second call: chains to first.
    child_id = await handler(
        RegenerateRunDebrief(run_id=run_id, parent_decision_id=parent_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert child_id == child_decision_id

    child = await load_decision(deps.event_store, child_id)
    assert child is not None
    assert child.parent_id == parent_id


@pytest.mark.integration
async def test_regenerate_run_debrief_idempotency_key_replay_returns_same_decision(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end Idempotency-Key replay through `wire_agent`'s
    Brandur envelope: two calls with the same key return the same
    decision_id, and the LLM is called exactly once. Closes a
    test-coverage gate-review action item."""
    from cora.agent.wire import wire_agent

    first_decision_id = uuid4()
    second_decision_id = uuid4()  # never used; cache hit returns first
    llm = FakeLLM(responses=[_CANNED_OK])
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[first_decision_id, second_decision_id],
        llm=llm,
    )
    await seed_run_debriefer_external_agent(deps)
    run_id = uuid4()
    await _seed_run(deps, run_id)

    bundle = wire_agent(deps)
    assert bundle.regenerate_run_debrief is not None, "kernel.llm wired -> handler non-None"

    idempotency_key = "test-regenerate-debrief-replay-key-001"
    first_id = await bundle.regenerate_run_debrief(
        RegenerateRunDebrief(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key=idempotency_key,
    )
    second_id = await bundle.regenerate_run_debrief(
        RegenerateRunDebrief(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key=idempotency_key,
    )

    # Same decision_id returned for both calls (replay via Brandur cache).
    assert first_id == second_id
    assert first_id == first_decision_id

    # LLM was called EXACTLY ONCE; second invocation came from cache.
    assert len(llm.received) == 1

    # Decision stream has exactly one event (the first write).
    events, version = await deps.event_store.load("Decision", first_id)
    assert version == 1
    assert len(events) == 1
