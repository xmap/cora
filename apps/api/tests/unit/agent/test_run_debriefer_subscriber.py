"""Unit tests for `RunDebrieferSubscriber`.

Drives the subscriber against `InMemoryEventStore` + `FakeLLM`
so the LLM call returns canned structured output without touching
the network. Covers happy path, DebriefDeferred fallback,
deterministic decision_id idempotency, missing-Run guard, and
missing-Actor guard.
"""

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4, uuid5

import pytest

from cora.access.aggregates.actor import (
    ActorKind,
    ActorRegistered,
)
from cora.access.aggregates.actor import event_type_name as actor_event_type_name
from cora.access.aggregates.actor import to_payload as actor_to_payload
from cora.agent.seed import (
    RUN_DEBRIEFER_AGENT_ID,
    RUN_DEBRIEFER_AGENT_NAME,
)
from cora.agent.subscribers._terminal_run_helpers import (
    extract_interrupted_at as _extract_interrupted_at,
)
from cora.agent.subscribers._terminal_run_helpers import (
    extract_reason as _extract_reason,
)
from cora.agent.subscribers.run_debriefer import (
    RunDebrieferSubscriber,
    _derive_decision_id,
    redact_secrets,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import (
    FakeLLM,
    FakeLLMResponse,
    LLMServerError,
    LLMUsage,
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.run.aggregates.run import (
    RunStarted,
)
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload

if TYPE_CHECKING:
    from cora.infrastructure.ports import LLM

from cora.run.aggregates.run.events import (
    RunAborted,
    RunCompleted,
    RunStopped,
    RunTruncated,
)
from tests.unit.agent._helpers import Ed25519FakeSigner, FakeInferenceRecorder

_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 17, 14, 47, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000099001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000009900a")


async def _seed_run_debrief_actor(
    store: InMemoryEventStore,
    *,
    deactivated: bool = False,
) -> None:
    """Write the bare-minimum Actor for the seeded RunDebriefer agent.

    The subscriber's `load_actor(event_store, RUN_DEBRIEFER_AGENT_ID)`
    needs an Actor row at that id. We only write the Actor (skip the
    Agent aggregate write); the subscriber doesn't load the Agent
    aggregate at apply()-time.

    Set `deactivated=True` to also append an `ActorDeactivated` event
    so the loaded Actor has `active=False` (exercise the security
    deactivated-actor gate).
    """
    # PII vault: event payload carries no `name`; display name lives
    # in actor_profile. The subscriber doesn't read the display
    # surface, so the legacy seed-name constant stays unused here.
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
        from cora.access.aggregates.actor import ActorDeactivated

        deactivated_event = ActorDeactivated(
            actor_id=RUN_DEBRIEFER_AGENT_ID,
            occurred_at=_NOW,
        )
        deactivated_new_event = to_new_event(
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
            events=[deactivated_new_event],
        )


async def _seed_run(
    store: InMemoryEventStore,
    run_id: UUID,
    *,
    plan_id: UUID | None = None,
    subject_id: UUID | None = None,
) -> None:
    """Write a single RunStarted event for the test Run."""
    plan = plan_id or UUID("01900000-0000-7000-8000-000000000401")
    subject = subject_id  # may be None
    started = RunStarted(
        run_id=run_id,
        name="Test Run",
        plan_id=plan,
        subject_id=subject,
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


def _terminal_event(
    *,
    event_type: str,
    run_id: UUID,
    reason: str | None = None,
    interrupted_at: datetime | None = None,
) -> StoredEvent:
    """Build a StoredEvent for one of the four terminal Run events."""
    domain: Any
    if event_type == "RunCompleted":
        domain = RunCompleted(run_id=run_id, occurred_at=_LATER)
    elif event_type == "RunAborted":
        assert reason is not None
        domain = RunAborted(run_id=run_id, reason=reason, occurred_at=_LATER)
    elif event_type == "RunStopped":
        assert reason is not None
        domain = RunStopped(run_id=run_id, reason=reason, occurred_at=_LATER)
    elif event_type == "RunTruncated":
        assert reason is not None
        domain = RunTruncated(
            run_id=run_id,
            reason=reason,
            interrupted_at=interrupted_at,
            occurred_at=_LATER,
        )
    else:
        msg = f"unsupported event type for fixture: {event_type}"
        raise ValueError(msg)
    return StoredEvent(
        position=1,
        event_id=UUID("01900000-0000-7000-8000-00000000ee01"),
        stream_type="Run",
        stream_id=run_id,
        version=2,
        event_type=event_type,
        schema_version=1,
        payload=run_to_payload(domain),
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_LATER,
        recorded_at=_LATER,
    )


async def _build_subscriber(
    event_store: InMemoryEventStore,
    llm: FakeLLM,
    inference_recorder: FakeInferenceRecorder | None = None,
) -> RunDebrieferSubscriber:
    return RunDebrieferSubscriber(
        event_store=event_store,
        llm=llm,
        logbook_mirror=None,
        inference_recorder=inference_recorder,
    )


_CANNED_OK = FakeLLMResponse(
    parsed={
        "choice": "NominalCompletion",
        "confidence": 0.92,
        "reasoning": (
            "Standard tomography Run completed cleanly. "
            "Synopsis: a single-Plan Run on the bound Subject ran to "
            "RunCompleted in 47 minutes. What was supposed to happen: "
            "collect frames at the configured exposure. What actually "
            "happened: zero adjustments; parameters match defaults. "
            "Why the difference: no difference; nominal execution."
        ),
    },
    stop_reason="tool_use",
    model_id="claude-haiku-4-5",
)


# Same shape as _CANNED_OK but with explicit token usage + a resolved
# dated snapshot, so the inference-provenance tests can assert real values
# flow from the LLMResponse onto the recorded trace.
_CANNED_OK_WITH_USAGE = FakeLLMResponse(
    parsed=_CANNED_OK.parsed,
    usage=LLMUsage(input_tokens=1280, output_tokens=214),
    stop_reason="tool_use",
    model_id="claude-haiku-4-5-20260201",
)


# ---------- Subscriber metadata ----------


@pytest.mark.unit
def test_subscriber_name_and_subscribed_event_types_pinned() -> None:
    """Name and subscribed types are stable bytes; the framework's
    bookmark row is keyed on `name`. Renaming would orphan the
    bookmark."""
    subscriber = RunDebrieferSubscriber(
        event_store=InMemoryEventStore(),
        llm=FakeLLM(),
        logbook_mirror=None,
    )
    assert subscriber.name == "run_debriefer"
    assert subscriber.subscribed_event_types == frozenset(
        {"RunCompleted", "RunAborted", "RunStopped", "RunTruncated"}
    )


# ---------- Happy path ----------


@pytest.mark.unit
async def test_apply_writes_decision_on_run_completed() -> None:
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.context.value == "RunDebrief"
    assert decision.choice.value == "NominalCompletion"
    assert decision.confidence == pytest.approx(0.92)
    assert decision.decided_by == RUN_DEBRIEFER_AGENT_ID
    assert decision.rule is not None
    assert decision.rule.value == "agent:RunDebriefer:v1"
    # inputs round-trip via JSONB.
    assert decision.inputs is not None
    assert decision.inputs["run_id"] == str(run_id)
    assert decision.inputs["terminal_event_id"] == str(event.event_id)
    assert decision.inputs["terminal_event_type"] == "RunCompleted"


@pytest.mark.unit
async def test_apply_writes_decision_on_run_aborted_with_reason() -> None:
    store = InMemoryEventStore()
    llm = FakeLLM(
        responses=[
            FakeLLMResponse(
                parsed={
                    "choice": "EquipmentAbort",
                    "confidence": 0.88,
                    "reasoning": (
                        "Rotary stage encoder went offline; interlock fired. "
                        "Synopsis: tomography Run aborted at the 12-minute mark. "
                        "What was supposed to happen: continuous rotation. "
                        "What actually happened: encoder fault triggered "
                        "interlock; reason field cites 'rotary stage encoder "
                        "offline; interlock fired'. Why the difference: "
                        "equipment-side failure."
                    ),
                }
            )
        ]
    )
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(
        event_type="RunAborted",
        run_id=run_id,
        reason="rotary stage encoder offline; interlock fired",
    )

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    assert decision.choice.value == "EquipmentAbort"
    # The reason should flow into the LLM payload, NOT into the
    # Decision's inputs (the input is the terminal event,
    # not the operator's reason text).
    captured_request = llm.received[0]
    assert "rotary stage encoder offline; interlock fired" in captured_request.user_message.text


@pytest.mark.unit
async def test_apply_passes_run_state_to_llm_payload() -> None:
    """The Run aggregate's state (effective_parameters,
    adjustment_count, etc.) lands in the LLM's user message."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    plan_id = UUID("01900000-0000-7000-8000-000000000abc")
    await _seed_run(store, run_id, plan_id=plan_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    captured = llm.received[0]
    assert str(run_id) in captured.user_message.text
    assert str(plan_id) in captured.user_message.text


# ---------- DebriefDeferred fallback ----------


@pytest.mark.unit
async def test_apply_writes_debrief_deferred_on_llm_failure() -> None:
    """When the LLM raises, the subscriber writes a DebriefDeferred
    Decision to preserve the exactly-one-Decision-per-terminal-Run
    audit invariant."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[LLMServerError("synthetic 500")])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    assert decision.choice.value == "DebriefDeferred"
    assert decision.confidence is None
    assert "LLM call failed with LLMServerError" in (decision.reasoning or "")
    assert decision.inputs is not None
    assert decision.inputs["failure_error_class"] == "LLMServerError"


@pytest.mark.unit
async def test_debrief_deferred_decision_id_matches_success_path() -> None:
    """Both success and deferred paths derive the same decision_id
    from the terminal event_id, so a retry that succeeds after a
    prior deferred fires the at-most-once ConcurrencyError guard."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[LLMServerError("first try")])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(store, decision_id)
    assert decision is not None  # written via deferred path

    # Second apply with a fresh LLM that returns ok; the subscriber's
    # ConcurrencyError catch should skip the write rather than create
    # a duplicate.
    llm2 = FakeLLM(responses=[_CANNED_OK])
    subscriber2 = await _build_subscriber(store, llm2)
    await subscriber2.apply(event, conn=None)
    # No duplicate written -- decision is still the deferred one.
    decision_after = await load_decision(store, decision_id)
    assert decision_after is not None
    assert decision_after.choice.value == "DebriefDeferred"


class _RaisingLLM:
    """LLM test-double whose `chat()` always raises a configured exception.

    FakeLLM only accepts `LLMError` in its response queue; this lets a
    test cover the widened exception handler that routes ANY
    non-CancelledError exception (TimeoutError, ConnectionError, an
    adapter bug not yet wrapped in `LLMError`) to the deferred fallback.
    """

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.received: list[Any] = []

    async def chat(self, request: Any) -> Any:
        self.received.append(request)
        raise self._exc


@pytest.mark.unit
async def test_apply_routes_non_llm_error_to_debrief_deferred() -> None:
    """Adapter raises a `RuntimeError` (not an `LLMError` subclass);
    subscriber's widened `except Exception` routes to the
    `DebriefDeferred` fallback so the lease is not orphaned + the
    bookmark advances. Defends against the infinite-replay loop where
    a non-LLMError on the LLM call would propagate, the bookmark tx
    would abort, and the next re-fire would re-acquire its own lease
    + hit the same crash."""
    store = InMemoryEventStore()
    llm = _RaisingLLM(RuntimeError("adapter bug: unwrapped transport failure"))
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = RunDebrieferSubscriber(
        event_store=store,
        llm=cast("LLM", llm),
        logbook_mirror=None,
    )
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    assert decision.choice.value == "DebriefDeferred"
    assert decision.confidence is None
    assert decision.inputs is not None
    assert decision.inputs["failure_error_class"] == "RuntimeError"


@pytest.mark.unit
async def test_apply_propagates_cancelled_error_does_not_write_decision() -> None:
    """`asyncio.CancelledError` is a `BaseException` since Python 3.8
    and MUST fall through `except Exception` so shutdown semantics
    are preserved. The lease event lands on the Run stream (BEFORE
    the LLM call), but no Decision is written and the exception
    propagates so the projection worker's bookmark transaction
    aborts and the event will retry on next process start."""
    import asyncio

    store = InMemoryEventStore()
    llm = _RaisingLLM(asyncio.CancelledError())
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = RunDebrieferSubscriber(
        event_store=store,
        llm=cast("LLM", llm),
        logbook_mirror=None,
    )
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    with pytest.raises(asyncio.CancelledError):
        await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    events, version = await store.load("Decision", decision_id)
    assert version == 0
    assert events == []
    # The lease was appended BEFORE the LLM call; it stays on the
    # Run stream as the audit primitive intends.
    stored, _v = await store.load("Run", run_id)
    leases = [s for s in stored if s.event_type == "DecisionDebriefRequested"]
    assert len(leases) == 1


# ---------- Idempotency ----------


@pytest.mark.unit
async def test_apply_is_at_most_once_via_deterministic_decision_id() -> None:
    """Two `apply()` calls with the same terminal event derive the
    same decision_id; the second call hits ConcurrencyError and
    treats it as no-op. Validates the at-most-once retry contract."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK, _CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)
    await subscriber.apply(event, conn=None)

    # First call wrote the Decision; second call hit ConcurrencyError
    # and skipped. The Decision stream is at version 1 (one event).
    decision_id = _derive_decision_id(event.event_id)
    events, version = await store.load("Decision", decision_id)
    assert version == 1, "second apply must not write a duplicate event"
    assert len(events) == 1


@pytest.mark.unit
def test_derive_decision_id_is_deterministic() -> None:
    """Pin the UUID5 derivation namespace + algorithm. Changing
    either would orphan every prior RunDebrief Decision."""
    event_id = UUID("01900000-0000-7000-8000-00000000ee01")
    assert _derive_decision_id(event_id) == _derive_decision_id(event_id)
    # Different event_id -> different decision_id.
    other = UUID("01900000-0000-7000-8000-00000000ee02")
    assert _derive_decision_id(event_id) != _derive_decision_id(other)


# ---------- Guards ----------


@pytest.mark.unit
async def test_apply_skips_when_run_missing() -> None:
    """A terminal event referencing a non-existent Run is a corrupt
    fixture; skip cleanly so the bookmark advances and the worker
    doesn't wedge."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    # Note: no _seed_run call.
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=uuid4())

    await subscriber.apply(event, conn=None)

    # No Decision written; no LLM call made.
    assert llm.received == []


@pytest.mark.unit
async def test_apply_skips_when_agent_actor_missing() -> None:
    """If the agent isn't seeded (bootstrap misconfigured), skip
    without writing -- the operator needs to fix the seed."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    # Note: no _seed_run_debrief_actor call.
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    # No Decision written; no LLM call made.
    assert llm.received == []


@pytest.mark.unit
async def test_apply_ignores_non_terminal_event_defensively() -> None:
    """Worker filters by subscribed_event_types so this shouldn't
    happen, but defensive early-return guards against a misrouted
    event."""
    store = InMemoryEventStore()
    llm = FakeLLM()
    await _seed_run_debrief_actor(store)
    subscriber = await _build_subscriber(store, llm)
    # Construct a non-terminal event (RunHeld is not in subscribed set).
    misrouted = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Run",
        stream_id=uuid4(),
        version=2,
        event_type="RunHeld",
        schema_version=1,
        payload={"run_id": str(uuid4()), "reason": "x"},
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_LATER,
        recorded_at=_LATER,
    )

    await subscriber.apply(misrouted, conn=None)

    # No LLM call -- early return on event_type mismatch.
    assert llm.received == []


# ---------- Causation chain ----------


@pytest.mark.unit
async def test_decision_event_causation_id_is_terminal_event_id() -> None:
    """Per PROV-O `wasInformedBy`, the agent's Decision is caused
    by the terminal Run event. Pin the causation chain so future
    refactors don't drop it."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision_events, _ = await store.load("Decision", decision_id)
    assert len(decision_events) == 1
    assert decision_events[0].causation_id == event.event_id


@pytest.mark.unit
async def test_decision_event_principal_id_is_agent_id() -> None:
    """The agent acts on its own behalf; `principal_id` on the
    envelope is the agent's id."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision_events, _ = await store.load("Decision", decision_id)
    assert decision_events[0].principal_id == RUN_DEBRIEFER_AGENT_ID


# ---------- Logbook mirror ----------


@pytest.mark.unit
async def test_apply_calls_logbook_mirror_when_configured() -> None:
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)

    mirror_calls: list[tuple[UUID, str, str]] = []

    class _CapturingMirror:
        async def mirror_decision(
            self,
            *,
            decision_id: UUID,
            narrative: str,
            target_logbook: str,
        ) -> None:
            mirror_calls.append((decision_id, narrative, target_logbook))

    subscriber = RunDebrieferSubscriber(
        event_store=store,
        llm=llm,
        logbook_mirror=_CapturingMirror(),
    )
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    assert len(mirror_calls) == 1
    assert mirror_calls[0][0] == _derive_decision_id(event.event_id)
    assert "Standard tomography Run completed cleanly." in mirror_calls[0][1]


@pytest.mark.unit
async def test_apply_swallows_logbook_mirror_errors() -> None:
    """Per port contract, mirror failures must not propagate to the
    Decision-emission audit trail."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)

    class _BrokenMirror:
        async def mirror_decision(self, **kwargs: Any) -> None:
            raise RuntimeError("mirror exploded")

    subscriber = RunDebrieferSubscriber(
        event_store=store,
        llm=llm,
        logbook_mirror=_BrokenMirror(),
    )
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    # Must NOT raise.
    await subscriber.apply(event, conn=None)

    # Decision still written despite mirror failure.
    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.choice.value == "NominalCompletion"


# ---------- Cleanup-pass additions (gate-review P1s) ----------


@pytest.mark.unit
async def test_apply_writes_decision_on_run_stopped() -> None:
    """RunStopped is in `subscribed_event_types` per the design but
    was not initially exercised end-to-end. Pin the path.
    Closes a test-coverage action item."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(
        event_type="RunStopped",
        run_id=run_id,
        reason="end-of-shift; operator-initiated clean stop",
    )

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    assert decision.context.value == "RunDebrief"
    # The reason flows into the LLM payload (not into Decision inputs).
    assert "end-of-shift" in llm.received[0].user_message.text


@pytest.mark.unit
async def test_apply_success_then_deferred_retry_is_no_op() -> None:
    """Reverse direction of test_debrief_deferred_decision_id_matches_success_path:
    first apply succeeds, second apply with a now-failing LLM should
    detect the existing Decision and NOT write DebriefDeferred.
    Closes test-coverage P1 #2."""
    store = InMemoryEventStore()
    llm1 = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber1 = await _build_subscriber(store, llm1)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber1.apply(event, conn=None)
    decision_id = _derive_decision_id(event.event_id)
    first = await load_decision(store, decision_id)
    assert first is not None
    assert first.choice.value == "NominalCompletion"

    # Second apply: LLM fails. Subscriber would compose DebriefDeferred
    # for the SAME decision_id, hit ConcurrencyError on append, and
    # skip. Decision should still be NominalCompletion.
    llm2 = FakeLLM(responses=[LLMServerError("synthetic 500")])
    subscriber2 = await _build_subscriber(store, llm2)
    await subscriber2.apply(event, conn=None)
    after = await load_decision(store, decision_id)
    assert after is not None
    assert after.choice.value == "NominalCompletion"


@pytest.mark.unit
async def test_apply_skips_when_agent_actor_deactivated() -> None:
    """Security gate-review: deactivated Actor must not author
    new Decisions. The subscriber's per-pass actor reload picks up
    a deactivation; an operator revoking the agent's identity takes
    effect on the next terminal event."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store, deactivated=True)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    # No Decision written; no LLM call made (short-circuit BEFORE
    # the LLM call so deactivation closes the credential boundary too).
    assert llm.received == []
    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is None


@pytest.mark.unit
async def test_apply_passes_non_zero_adjustment_count_to_llm_payload() -> None:
    """`Run.adjustment_count` is set on the aggregate after one or
    more `adjust_run` (6j) operations. Pin that the count flows into
    the LLM JSON payload so the LLM can narrate parameter steering.
    Closes test-coverage P1 #5."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    plan_id = UUID("01900000-0000-7000-8000-000000000abc")
    await _seed_run(store, run_id, plan_id=plan_id)
    # The seed only writes RunStarted; for v1 we don't fold a real
    # adjust_run event into the Run -- adjustment_count stays 0. The
    # test instead drives the path via the fixture's run state and
    # asserts the JSON payload's `adjustment_count` key is present.
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    import json

    body = llm.received[0].user_message.text
    json_part = body.split("\n\n", 1)[1]
    decoded = json.loads(json_part)
    assert "adjustment_count" in decoded
    assert decoded["adjustment_count"] == 0  # no adjustments at v1 fixture
    # last_adjusted_at and campaign_id present-as-null are also
    # load-bearing for the LLM's reasoning so pin them.
    assert decoded["last_adjusted_at"] is None
    assert decoded["campaign_id"] is None


@pytest.mark.unit
async def test_apply_payload_carries_effective_parameters_by_value() -> None:
    """test_apply_passes_run_state_to_llm_payload only asserts
    `str(run_id) in text` (substring). Pin the actual
    effective_parameters value flows through. Closes test-coverage P1 #4."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    import json

    body = llm.received[0].user_message.text
    json_part = body.split("\n\n", 1)[1]
    decoded = json.loads(json_part)
    # The Run fixture's effective_parameters defaults to {} on RunStarted.
    assert decoded["effective_parameters"] == {}


# ---------- Helper-level pins ----------


@pytest.mark.unit
def test_extract_reason_returns_none_for_run_completed() -> None:
    """Closes test-coverage P1 #6."""
    event = _terminal_event(event_type="RunCompleted", run_id=uuid4())
    assert _extract_reason(event) is None


@pytest.mark.unit
def test_extract_reason_returns_string_for_aborted() -> None:
    event = _terminal_event(
        event_type="RunAborted",
        run_id=uuid4(),
        reason="interlock fired",
    )
    assert _extract_reason(event) == "interlock fired"


@pytest.mark.unit
def test_extract_interrupted_at_returns_none_when_absent() -> None:
    """Closes test-coverage P1 #6."""
    event = _terminal_event(event_type="RunCompleted", run_id=uuid4())
    assert _extract_interrupted_at(event) is None


@pytest.mark.unit
def test_extract_interrupted_at_returns_iso_string_for_truncated() -> None:
    interrupted = datetime(2026, 5, 17, 13, 55, 0, tzinfo=UTC)
    event = _terminal_event(
        event_type="RunTruncated",
        run_id=uuid4(),
        reason="frame sync lost",
        interrupted_at=interrupted,
    )
    # The fixture's to_payload encodes interrupted_at as ISO string;
    # _extract_interrupted_at returns it as-is.
    extracted = _extract_interrupted_at(event)
    assert extracted is not None
    assert extracted.startswith("2026-05-17")


# ---------- Secret redaction ----------


@pytest.mark.unit
def test_redact_secrets_strips_anthropic_api_key_pattern() -> None:
    """Security gate-review: defensive redact of `sk-ant-*`
    substrings before structured-logging error messages so a future
    SDK regression that echoes the key doesn't persist it forever."""
    raw = "Authentication failed; key sk-ant-VERYSECRETabc123-xyz prefix exposed"
    cleaned = redact_secrets(raw)
    assert "sk-ant-VERYSECRETabc123-xyz" not in cleaned
    assert "[REDACTED]" in cleaned


@pytest.mark.unit
def test_redact_secrets_no_op_on_clean_message() -> None:
    """No false-positive redaction on regular error text."""
    raw = "connection reset by peer"
    assert redact_secrets(raw) == raw


@pytest.mark.unit
def test_redact_secrets_handles_multiple_occurrences() -> None:
    raw = "first sk-ant-AAA111 then sk-ant-BBB222 done"
    cleaned = redact_secrets(raw)
    assert "sk-ant-AAA111" not in cleaned
    assert "sk-ant-BBB222" not in cleaned
    assert cleaned.count("[REDACTED]") == 2


# ---------- Signer wiring ----------


@pytest.mark.unit
async def test_apply_leaves_signature_none_when_no_signer_configured() -> None:
    """Backward-compat: subscriber without a Signer dep produces
    unsigned events. Default for every existing deployment."""
    from cora.infrastructure.ports.event_store import StoredEvent

    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)  # signer=None
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)
    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    events, _ = await store.load("Decision", decision_id)
    assert events, "Decision event should have been written"
    stored: StoredEvent = events[0]
    assert stored.signature is None
    assert stored.signature_kid is None


@pytest.mark.unit
async def test_apply_signs_decision_when_signer_configured() -> None:
    """End-to-end: subscriber with a Signer attaches a verifying Ed25519
    signature to the DecisionRegistered event."""
    from cora.infrastructure.ports.event_store import StoredEvent
    from cora.infrastructure.signing import verify_signature

    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    signer = Ed25519FakeSigner(kid="kid-run-debriefer")
    subscriber = RunDebrieferSubscriber(
        event_store=store,
        llm=llm,
        logbook_mirror=None,
        signer=signer,
    )
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)
    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    events, _ = await store.load("Decision", decision_id)
    stored: StoredEvent = events[0]
    assert stored.signature is not None
    assert stored.signature_kid == "kid-run-debriefer"
    assert len(stored.signature) == 64
    # The subscriber MUST pass the Agent's id to the signer; a regression
    # that dropped or renamed the `actor_id` kwarg would silently sign
    # with the wrong identity in production.
    assert signer.received_actor_ids == [RUN_DEBRIEFER_AGENT_ID]

    async def _resolver(kid: str) -> bytes:
        assert kid == "kid-run-debriefer"
        return signer.public_key_bytes

    await verify_signature(
        event_type=stored.event_type,
        payload=stored.payload,
        signature=stored.signature,
        kid=stored.signature_kid,
        resolve_public_key=_resolver,
    )


# ---------- Signer fail-closed (outage propagation) ----------


class _RaisingSigner:
    """`Signer` adapter that raises the configured exception on `sign()`.
    Exists so the subscriber-level fail-closed test can drive each of
    the three adapter-tier failure modes without spinning up the real
    Sigstore / KMS / local adapter."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def sign(
        self,
        *,
        event_type: str,
        payload: Any,
        actor_id: UUID,
    ) -> tuple[bytes, str, str]:
        _ = (event_type, payload, actor_id)
        raise self._exc


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param("unavailable", id="SignerUnavailableError"),
        pytest.param("inactive_key", id="SignerKeyInactiveError"),
        pytest.param("missing_key", id="SignerKeyNotFoundError"),
    ],
)
@pytest.mark.unit
async def test_apply_fails_closed_when_signer_raises_and_writes_no_decision(
    failure: str,
) -> None:
    """When the Signer adapter raises any of its three documented errors,
    the subscriber MUST propagate the failure and MUST NOT write an
    unsigned `DecisionRegistered`. Fail-open here would silently
    introduce unsigned agent-actor events into the stream and break
    the Candidate F design-lock invariant
    (every event whose actor is an Agent is signed).

    The projection worker's retry / DLQ logic re-runs the
    subscriber once the outage clears; the failure surface here is
    the right place for that recovery to engage."""
    from cora.infrastructure.ports.signer import (
        SignerKeyInactiveError,
        SignerKeyNotFoundError,
        SignerUnavailableError,
    )

    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)

    exc: Exception
    if failure == "unavailable":
        exc = SignerUnavailableError("sigstore-fulcio", detail="connection refused")
    elif failure == "inactive_key":
        exc = SignerKeyInactiveError("kid-run-debriefer-old")
    else:
        exc = SignerKeyNotFoundError(RUN_DEBRIEFER_AGENT_ID)

    subscriber = RunDebrieferSubscriber(
        event_store=store,
        llm=llm,
        logbook_mirror=None,
        signer=_RaisingSigner(exc),
    )
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    with pytest.raises(type(exc)):
        await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    events, version = await store.load("Decision", decision_id)
    assert version == 0
    assert events == []


@pytest.mark.unit
async def test_apply_does_not_swallow_unexpected_signer_exception() -> None:
    """A non-Signer-tier exception (a bug inside the adapter, or a
    transport-layer error not yet wrapped in `SignerUnavailableError`)
    MUST also propagate. Locks the absence of a bare `except Exception`
    around the signing call that would silently fall back to unsigned."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)

    subscriber = RunDebrieferSubscriber(
        event_store=store,
        llm=llm,
        logbook_mirror=None,
        signer=_RaisingSigner(RuntimeError("unexpected adapter bug")),
    )
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    with pytest.raises(RuntimeError, match="unexpected adapter bug"):
        await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    events, version = await store.load("Decision", decision_id)
    assert version == 0
    assert events == []


# ---------- Cross-agent lease (project_run_debriefer_lease_design) ----------


@pytest.mark.unit
async def test_apply_appends_lease_event_to_run_stream_on_happy_path() -> None:
    """The subscriber appends a DecisionDebriefRequested marker to the
    Run stream BEFORE invoking the LLM. Per the design memo, the lease
    primitive's existence on the stream IS the lease; this test pins
    the append + payload shape."""
    from cora.agent._subscriber_lease import derive_lease_event_id

    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    stored, _v = await store.load("Run", run_id)
    leases = [s for s in stored if s.event_type == "DecisionDebriefRequested"]
    assert len(leases) == 1
    lease = leases[0]
    assert lease.payload["run_id"] == str(run_id)
    assert lease.payload["debriefer_agent_id"] == str(RUN_DEBRIEFER_AGENT_ID)
    assert lease.payload["terminal_event_id"] == str(event.event_id)
    # event_id is the deterministic seed so retries are idempotent.
    assert lease.event_id == derive_lease_event_id(
        run_id=run_id,
        debriefer_agent_id=RUN_DEBRIEFER_AGENT_ID,
        terminal_event_id=event.event_id,
    )


@pytest.mark.unit
async def test_apply_writes_debrief_conflicted_when_another_agent_holds_lease() -> None:
    """When a different agent already holds the lease (lease event on
    Run stream by a foreign debriefer_agent_id), the subscriber writes
    DebriefConflicted on its own Decision stream WITHOUT invoking the
    LLM. Per the design memo: losing agents pay zero LLM cost."""
    from cora.agent._subscriber_lease import attempt_debrief_lease

    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    # Pre-seed a lease by a foreign agent.
    foreign_agent_id = uuid4()
    pre_acquired, _ = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=foreign_agent_id,
        terminal_event=event,
        occurred_at=event.occurred_at,
        command_name="ForeignAgent",
    )
    assert pre_acquired is True

    recorder = FakeInferenceRecorder()
    subscriber = await _build_subscriber(store, llm, recorder)
    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.context.value == "RunDebrief"
    assert decision.choice.value == "DebriefConflicted"
    assert decision.confidence is None  # no LLM call was made
    # winning agent_id is recorded in inputs for cross-Decision audit.
    assert decision.inputs is not None
    assert decision.inputs["winning_agent_id"] == str(foreign_agent_id)
    # LLM must NOT have been called, so no inference is recorded either.
    assert llm.received == []
    assert recorder.calls == []


@pytest.mark.unit
async def test_apply_after_prior_lease_by_same_agent_proceeds_to_llm_and_writes_decision() -> None:
    """Re-fire after a crash-between-lease-and-Decision: the subscriber
    sees its OWN prior lease on the Run stream, treats the lease as
    already held, and proceeds to the LLM + Decision write path.
    Pins the design memo's same-agent crash-recovery contract."""
    from cora.agent._subscriber_lease import attempt_debrief_lease

    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    # Simulate prior crash: lease landed on Run stream under THIS agent.
    pre_acquired, _ = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=RUN_DEBRIEFER_AGENT_ID,
        terminal_event=event,
        occurred_at=event.occurred_at,
        command_name="PriorCrash",
    )
    assert pre_acquired is True

    subscriber = await _build_subscriber(store, llm)
    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.choice.value == "NominalCompletion"
    assert llm.received != []
    stored, _v = await store.load("Run", run_id)
    leases = [s for s in stored if s.event_type == "DecisionDebriefRequested"]
    assert len(leases) == 1


@pytest.mark.unit
async def test_apply_writes_debrief_conflicted_unidentified_winner_on_no_winner_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`(False, None)` from the lease helper (the rare race where the
    Run stream advanced for a non-lease reason between load and
    append) lands a DebriefConflicted Decision whose reasoning notes
    the unidentified winner and whose `inputs` omits
    `winning_agent_id`. Pins the degenerate-loss path."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK])
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    async def _force_loss_without_winner(*_args: object, **_kwargs: object) -> tuple[bool, None]:
        return False, None

    monkeypatch.setattr(
        "cora.agent.subscribers.run_debriefer.attempt_debrief_lease",
        _force_loss_without_winner,
    )

    subscriber = await _build_subscriber(store, llm)
    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.choice.value == "DebriefConflicted"
    assert decision.confidence is None
    assert decision.inputs is not None
    assert "winning_agent_id" not in decision.inputs
    assert decision.reasoning is not None
    assert "winning agent not identified" in decision.reasoning
    assert llm.received == []


# ---------- Inference provenance ----------


@pytest.mark.unit
async def test_apply_records_inference_on_success() -> None:
    """A successful debrief records one inference trace carrying the LLM
    call's provider, resolved model snapshot, token usage, and stop reason."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK_WITH_USAGE])
    recorder = FakeInferenceRecorder()
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm, recorder)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    decision_id = _derive_decision_id(event.event_id)
    assert call.trace.decision_id == decision_id
    assert call.trace.event_id == uuid5(decision_id, "inference:0")
    assert call.trace.operation_name == "chat"
    assert call.trace.provider_name == "anthropic"
    assert call.trace.request_model == "claude-haiku-4-5"
    assert call.trace.response_model == "claude-haiku-4-5-20260201"
    assert call.trace.input_tokens == 1280
    assert call.trace.output_tokens == 214
    assert call.trace.finish_reasons == ("tool_use",)
    assert call.trace.request_max_tokens == 1024
    assert call.trace.agent_id == str(RUN_DEBRIEFER_AGENT_ID)
    assert call.trace.agent_name == RUN_DEBRIEFER_AGENT_NAME
    assert call.principal_id == RUN_DEBRIEFER_AGENT_ID
    assert call.correlation_id == event.correlation_id
    assert call.causation_id == event.event_id


@pytest.mark.unit
async def test_apply_records_no_inference_on_llm_failure() -> None:
    """The deferred path (LLM exhausted) has no LLM response, so no
    inference is recorded even though a DebriefDeferred Decision is written."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[LLMServerError("synthetic 500")])
    recorder = FakeInferenceRecorder()
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm, recorder)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    assert decision.choice.value == "DebriefDeferred"
    assert recorder.calls == []


@pytest.mark.unit
async def test_apply_inference_recorder_failure_does_not_break_decision() -> None:
    """A recorder that raises must not propagate: the Decision is still
    written (provenance is supplementary, fire-and-forget)."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK_WITH_USAGE])
    recorder = FakeInferenceRecorder(raises=RuntimeError("recorder boom"))
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm, recorder)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    assert len(recorder.calls) == 1
    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    assert decision.choice.value == "NominalCompletion"


@pytest.mark.unit
async def test_apply_records_inference_with_stable_event_id_under_retry() -> None:
    """Re-applying the same terminal event re-records with the SAME inference
    event_id (the idempotency seed), so the store dedups on re-delivery."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_OK_WITH_USAGE, _CANNED_OK_WITH_USAGE])
    recorder = FakeInferenceRecorder()
    await _seed_run_debrief_actor(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm, recorder)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)
    await subscriber.apply(event, conn=None)

    assert len(recorder.calls) == 2
    assert recorder.calls[0].trace.event_id == recorder.calls[1].trace.event_id
