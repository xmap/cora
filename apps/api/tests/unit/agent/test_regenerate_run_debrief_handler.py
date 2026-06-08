"""Application-handler tests for `regenerate_run_debrief`.

Drives the on-demand RunDebrief handler against InMemoryEventStore +
FakeLLM. Covers happy path, DebriefDeferred-on-LLM-failure,
Run/Agent/parent-Decision pre-load guards, Actor-deactivated gate,
parent-Run-mismatch validation, authorize-deny, and the bind-time
RuntimeError when kernel.llm is unwired.
"""

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.access.aggregates.actor import (
    ActorDeactivated,
    ActorKind,
    ActorRegistered,
)
from cora.access.aggregates.actor import event_type_name as actor_event_type_name
from cora.access.aggregates.actor import to_payload as actor_to_payload
from cora.agent.aggregates.agent import AgentDeactivatedError, AgentNotSeededError
from cora.agent.errors import UnauthorizedError
from cora.agent.features import regenerate_run_debrief
from cora.agent.features.regenerate_run_debrief import RegenerateRunDebrief
from cora.agent.features.regenerate_run_debrief.handler import bind
from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID, RUN_DEBRIEFER_AGENT_NAME
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_DEBRIEF,
    DecisionParentAgentMismatchError,
    DecisionParentNotFoundError,
    DecisionParentRunMismatchError,
    load_decision,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import (
    FakeLLM,
    FakeLLMResponse,
    LLMServerError,
)
from cora.run.aggregates.run import RunNotFoundError, RunStarted
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 17, 16, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000088001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000008800a")
_NEW_DECISION_ID = UUID("01900000-0000-7000-8000-00000000fc01")


async def _seed_actor(store: InMemoryEventStore, *, deactivated: bool = False) -> None:
    # PII vault: V2 payload carries no `name`; the display name lives
    # in actor_profile. These tests don't read the display surface, so
    # they don't seed the vault — RUN_DEBRIEFER_AGENT_NAME stays unused
    # by the event itself.
    _ = RUN_DEBRIEFER_AGENT_NAME
    event = ActorRegistered(
        actor_id=RUN_DEBRIEFER_AGENT_ID,
        occurred_at=_NOW,
        kind=ActorKind.AGENT,
    )
    new_event = to_new_event(
        event_type=actor_event_type_name(event),
        payload=actor_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="SeedTestAgent",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Actor",
        stream_id=RUN_DEBRIEFER_AGENT_ID,
        expected_version=0,
        events=[new_event],
    )
    if deactivated:
        deactivated_event = ActorDeactivated(
            actor_id=RUN_DEBRIEFER_AGENT_ID,
            occurred_at=_NOW,
        )
        deactivated_new = to_new_event(
            event_type=actor_event_type_name(deactivated_event),
            payload=actor_to_payload(deactivated_event),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="DeactivateTestAgent",
            correlation_id=_CORRELATION_ID,
            causation_id=None,
            principal_id=_PRINCIPAL_ID,
        )
        await store.append(
            stream_type="Actor",
            stream_id=RUN_DEBRIEFER_AGENT_ID,
            expected_version=1,
            events=[deactivated_new],
        )


async def _seed_run(store: InMemoryEventStore, run_id: UUID) -> None:
    started = RunStarted(
        run_id=run_id,
        name="Test Run",
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
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[new_event],
    )


_CANNED_OK = FakeLLMResponse(
    parsed={
        "choice": "NominalCompletion",
        "confidence": 0.88,
        "reasoning": (
            "On-demand debrief regeneration: Run completed nominally. Synopsis: a "
            "single-Plan tomography Run on the bound Subject ran to "
            "RunCompleted. What was supposed to happen: standard scan with "
            "no adjustments. What actually happened: the Run terminated "
            "cleanly with effective_parameters matching defaults. Why "
            "the difference: no difference; operator re-triggered for a "
            "fresh narrative after rating the prior as misleading."
        ),
    },
    stop_reason="tool_use",
    model_id="claude-haiku-4-5",
)


# ---------- Bind-time gate ----------


@pytest.mark.unit
def test_bind_raises_runtime_error_when_llm_unwired() -> None:
    """The slice has no useful behavior without an LLM; fail loud
    at bind() rather than silently noop at handler-call time."""
    deps = build_deps(ids=[_NEW_DECISION_ID], now=_NOW, llm=None)
    with pytest.raises(RuntimeError, match=r"kernel\.llm"):
        bind(deps)


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_writes_decision_on_success() -> None:
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    run_id = uuid4()
    await _seed_actor(store)
    await _seed_run(store, run_id)
    deps = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler = bind(deps)

    decision_id = await handler(
        RegenerateRunDebrief(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert decision_id == _NEW_DECISION_ID
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.context.value == DECISION_CONTEXT_RUN_DEBRIEF
    assert decision.choice.value == "NominalCompletion"
    assert decision.decided_by == RUN_DEBRIEFER_AGENT_ID
    assert decision.parent_id is None
    # inputs carries the trigger discriminator so projection
    # consumers can distinguish on-demand vs auto-fired Decisions.
    assert decision.inputs is not None
    assert decision.inputs["trigger"] == "on-demand"
    assert decision.inputs["run_id"] == str(run_id)


@pytest.mark.unit
async def test_handler_envelope_principal_id_is_operator_not_agent() -> None:
    """Crucial security property: on-demand `principal_id` is the
    operator (HTTP header), NOT the agent's own id. Distinct from
    the subscriber where principal_id == actor_id."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    run_id = uuid4()
    await _seed_actor(store)
    await _seed_run(store, run_id)
    deps = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler = bind(deps)

    await handler(
        RegenerateRunDebrief(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Decision", _NEW_DECISION_ID)
    assert len(events) == 1
    assert events[0].principal_id == _PRINCIPAL_ID
    assert events[0].principal_id != RUN_DEBRIEFER_AGENT_ID


@pytest.mark.unit
async def test_handler_chains_parent_decision_when_supplied() -> None:
    """Operator-supplied parent_decision_id sets `Decision.parent_id`
    (PROV-O wasInformedBy)."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK, _CANNED_OK])
    run_id = uuid4()
    await _seed_actor(store)
    await _seed_run(store, run_id)

    # First call: standalone Decision.
    deps1 = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler1 = bind(deps1)
    parent_decision_id = await handler1(
        RegenerateRunDebrief(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Second call: chains to the first.
    second_id = UUID("01900000-0000-7000-8000-00000000fc02")
    deps2 = build_deps(
        ids=[second_id],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler2 = bind(deps2)
    child_decision_id = await handler2(
        RegenerateRunDebrief(run_id=run_id, parent_decision_id=parent_decision_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    child = await load_decision(store, child_decision_id)
    assert child is not None
    assert child.parent_id == parent_decision_id


# ---------- Cross-aggregate guards ----------


@pytest.mark.unit
async def test_handler_raises_run_missing_when_run_absent() -> None:
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_actor(store)
    # No _seed_run call.
    deps = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler = bind(deps)

    with pytest.raises(RunNotFoundError):
        await handler(
            RegenerateRunDebrief(run_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # No LLM call made.
    assert llm.received == []


@pytest.mark.unit
async def test_handler_raises_agent_not_seeded_when_actor_absent() -> None:
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    run_id = uuid4()
    await _seed_run(store, run_id)
    # No _seed_actor call.
    deps = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler = bind(deps)

    with pytest.raises(AgentNotSeededError):
        await handler(
            RegenerateRunDebrief(run_id=run_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert llm.received == []


@pytest.mark.unit
async def test_handler_raises_agent_deactivated_when_actor_inactive() -> None:
    """Security: a deactivated agent Actor cannot author on-demand
    Decisions. Mirrors the subscriber's Actor.active gate."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    run_id = uuid4()
    await _seed_actor(store, deactivated=True)
    await _seed_run(store, run_id)
    deps = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler = bind(deps)

    with pytest.raises(AgentDeactivatedError):
        await handler(
            RegenerateRunDebrief(run_id=run_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert llm.received == []


@pytest.mark.unit
async def test_handler_raises_parent_missing_when_parent_absent() -> None:
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    run_id = uuid4()
    await _seed_actor(store)
    await _seed_run(store, run_id)
    deps = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler = bind(deps)

    bogus_parent = uuid4()
    with pytest.raises(DecisionParentNotFoundError):
        await handler(
            RegenerateRunDebrief(run_id=run_id, parent_decision_id=bogus_parent),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert llm.received == []


@pytest.mark.unit
async def test_handler_raises_parent_run_mismatch_for_cross_run_chain() -> None:
    """The parent Decision must reference the same Run as the
    command. Prevents an accidental "regenerate Run B's debrief as a
    child of Run A's prior Debrief" miswire."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK, _CANNED_OK])
    run_a = uuid4()
    run_b = uuid4()
    await _seed_actor(store)
    await _seed_run(store, run_a)
    await _seed_run(store, run_b)

    # Write a Decision for Run A.
    deps1 = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler1 = bind(deps1)
    run_a_decision_id = await handler1(
        RegenerateRunDebrief(run_id=run_a),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Try to chain it under Run B; must reject.
    second_id = UUID("01900000-0000-7000-8000-00000000fc03")
    deps2 = build_deps(
        ids=[second_id],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler2 = bind(deps2)
    with pytest.raises(DecisionParentRunMismatchError):
        await handler2(
            RegenerateRunDebrief(run_id=run_b, parent_decision_id=run_a_decision_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_parent_agent_mismatch_for_non_run_debrief_parent() -> None:
    """The parent Decision must have `context = "RunDebrief"`.

    Closes an architecture gate-review action item: prevents
    accidental cross-agent chains where the operator passes a
    Decision id authored by a different agent (eg. a `PolicyGrant`
    Decision)."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    run_id = uuid4()
    await _seed_actor(store)
    await _seed_run(store, run_id)

    # Seed a Decision with `context = "OtherAgent"` (NOT "RunDebrief").
    foreign_decision_id = UUID("01900000-0000-7000-8000-00000000fcaa")
    await _seed_foreign_context_decision(store, foreign_decision_id, run_id)

    deps = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler = bind(deps)
    with pytest.raises(DecisionParentAgentMismatchError):
        await handler(
            RegenerateRunDebrief(run_id=run_id, parent_decision_id=foreign_decision_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Short-circuits BEFORE the LLM call.
    assert llm.received == []


async def _seed_foreign_context_decision(
    store: InMemoryEventStore,
    decision_id: UUID,
    run_id: UUID,
) -> None:
    """Helper: write a `DecisionRegistered` event with `context !=
    "RunDebrief"` and `inputs["run_id"]` set to the test's
    run_id. Used to test the agent-mismatch guard without polluting
    the cross-aggregate test setup."""
    from cora.decision.aggregates.decision import DecisionRegistered
    from cora.decision.aggregates.decision import event_type_name as decision_event_type_name
    from cora.decision.aggregates.decision import to_payload as decision_to_payload

    domain_event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(uuid4()),  # some other actor
        context="OtherAgent",
        choice="SomeChoice",
        parent_id=None,
        override_kind=None,
        rule=None,
        reasoning=None,
        confidence=None,
        confidence_source=None,
        alternatives=(),
        inputs={"run_id": str(run_id)},
        reasoning_signature=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=decision_event_type_name(domain_event),
        payload=decision_to_payload(domain_event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="SeedTestForeignContextDecision",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Decision",
        stream_id=decision_id,
        expected_version=0,
        events=[new_event],
    )


# ---------- DebriefDeferred fallback ----------


@pytest.mark.unit
async def test_handler_writes_debrief_deferred_on_llm_failure() -> None:
    """LLM exhaust path: write DebriefDeferred Decision, return its id."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[LLMServerError("synthetic 500")])
    run_id = uuid4()
    await _seed_actor(store)
    await _seed_run(store, run_id)
    deps = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
    )
    handler = bind(deps)

    decision_id = await handler(
        RegenerateRunDebrief(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert decision_id == _NEW_DECISION_ID
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.choice.value == "DebriefDeferred"
    assert decision.confidence is None
    assert decision.inputs is not None
    assert decision.inputs["failure_error_class"] == "LLMServerError"


# ---------- Authorize gate ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_when_authz_denies() -> None:
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    run_id = uuid4()
    await _seed_actor(store)
    await _seed_run(store, run_id)
    deps = build_deps(
        ids=[_NEW_DECISION_ID],
        now=_NOW,
        event_store=store,
        llm=llm,
        deny=True,
    )
    handler = bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            RegenerateRunDebrief(run_id=run_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Authorize denial short-circuits BEFORE any load.
    assert llm.received == []


# ---------- Slice re-export contract ----------


@pytest.mark.unit
def test_slice_reexports_command_handler_and_router() -> None:
    """Pin the slice's public surface so the routes / wire-up
    refactor doesn't accidentally drop a re-export."""
    assert hasattr(regenerate_run_debrief, "RegenerateRunDebrief")
    assert hasattr(regenerate_run_debrief, "bind")
    assert hasattr(regenerate_run_debrief, "Handler")
    assert hasattr(regenerate_run_debrief, "IdempotentHandler")
    assert hasattr(regenerate_run_debrief, "router")
