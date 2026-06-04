"""Unit tests for `CautionDrafterSubscriber`.

Drives the subscriber against `InMemoryEventStore` + `FakeLLM`
+ `AlwaysQuietCautionLookup` so the LLM call returns canned
structured output without touching the network. Covers happy path,
NoAction fallback on LLM exhaust, deterministic-decision_id
idempotency, missing-Plan guard, missing-Actor guard, deactivated-
Actor gate, and schema-violation fallback.

Mirrors `test_run_debrief_subscriber.py` structure.
"""

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.access.aggregates.actor import (
    ActorKind,
    ActorRegistered,
)
from cora.access.aggregates.actor import event_type_name as actor_event_type_name
from cora.access.aggregates.actor import to_payload as actor_to_payload
from cora.agent.seed_caution_drafter import (
    CAUTION_DRAFTER_AGENT_ID,
    CAUTION_DRAFTER_AGENT_NAME,
)
from cora.agent.subscribers.caution_drafter import (
    CautionDrafterSubscriber,
    _coerce_proposed_caution,
    _derive_decision_id,
    _proposed_target_in_candidates,
    make_caution_drafter_subscriber,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import (
    AlwaysQuietCautionLookup,
    FakeLLM,
    FakeLLMResponse,
    LLMServerError,
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.plan import (
    PlanDefined,
)
from cora.recipe.aggregates.plan import event_type_name as plan_event_type_name
from cora.recipe.aggregates.plan import to_payload as plan_to_payload
from cora.run.aggregates.run import RunStarted
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload
from cora.run.aggregates.run.events import (
    RunAborted,
    RunCompleted,
)
from tests.unit._helpers import build_deps
from tests.unit.agent._helpers import Ed25519FakeSigner

_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 17, 14, 47, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000099001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000009900a")

# A canned Plan id (Plan must exist for the subscriber to proceed).
_PLAN_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-00000000bbbb")
_METHOD_ID = UUID("01900000-0000-7000-8000-00000000cccc")
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000dddd")


# ---------------------------------------------------------------------------
# Test fixtures: seed helpers
# ---------------------------------------------------------------------------


async def _seed_caution_drafter_actor(
    store: InMemoryEventStore,
    *,
    deactivated: bool = False,
) -> None:
    """Write the minimum Actor for the seeded CautionDrafter agent.

    PII vault: V2 payload carries no `name`; display name lives in
    `actor_profile`. Subscriber tests don't read the display
    surface, so the seed name stays unused at the event layer.
    """
    _ = CAUTION_DRAFTER_AGENT_NAME
    event = ActorRegistered(
        actor_id=CAUTION_DRAFTER_AGENT_ID,
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
        stream_id=CAUTION_DRAFTER_AGENT_ID,
        expected_version=0,
        events=[new_event],
    )
    if deactivated:
        from cora.access.aggregates.actor import ActorDeactivated

        d_event = ActorDeactivated(
            actor_id=CAUTION_DRAFTER_AGENT_ID,
            occurred_at=_NOW,
        )
        d_new_event = to_new_event(
            event_type=actor_event_type_name(d_event),
            payload=actor_to_payload(d_event),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="DeactivateTestAgent",
            correlation_id=_CORRELATION_ID,
            causation_id=None,
            principal_id=_PRINCIPAL_ID,
        )
        await store.append(
            stream_type="Actor",
            stream_id=CAUTION_DRAFTER_AGENT_ID,
            expected_version=1,
            events=[d_new_event],
        )


async def _seed_plan(store: InMemoryEventStore, *, plan_id: UUID = _PLAN_ID) -> None:
    """Write a PlanDefined event so the subscriber's Plan load succeeds."""
    plan = PlanDefined(
        plan_id=plan_id,
        name="Test Plan",
        practice_id=_PRACTICE_ID,
        asset_ids=(_ASSET_ID,),
        method_id=_METHOD_ID,
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={_ASSET_ID: ()},
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=plan_event_type_name(plan),
        payload=plan_to_payload(plan),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DefinePlan",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Plan",
        stream_id=plan_id,
        expected_version=0,
        events=[new_event],
    )


async def _seed_run(
    store: InMemoryEventStore,
    run_id: UUID,
    *,
    plan_id: UUID = _PLAN_ID,
) -> None:
    """Write a single RunStarted event for the test Run."""
    started = RunStarted(
        run_id=run_id,
        name="Test Run",
        plan_id=plan_id,
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


def _terminal_event(
    *,
    event_type: str,
    run_id: UUID,
    reason: str | None = None,
) -> StoredEvent:
    """Build a StoredEvent for a terminal Run event."""
    domain: Any
    if event_type == "RunCompleted":
        domain = RunCompleted(run_id=run_id, occurred_at=_LATER)
    elif event_type == "RunAborted":
        assert reason is not None
        domain = RunAborted(run_id=run_id, reason=reason, occurred_at=_LATER)
    else:
        msg = f"unsupported event type for fixture: {event_type}"
        raise ValueError(msg)
    return StoredEvent(
        position=1,
        event_id=UUID("01900000-0000-7000-8000-00000000ff01"),
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
) -> CautionDrafterSubscriber:
    return CautionDrafterSubscriber(
        event_store=event_store,
        llm=llm,
        caution_lookup=AlwaysQuietCautionLookup(),
    )


_CANNED_NO_ACTION = FakeLLMResponse(
    parsed={
        "choice": "NoAction",
        "confidence": 0.85,
        "confidence_band": "high",
        "reasoning": (
            "Run completed nominally with no signs of distress; no new "
            "tribal-knowledge signal worth surfacing as a Caution. "
            "Default-refuse per the prompt's aggressive-refusal rule."
        ),
    },
    stop_reason="tool_use",
    model_id="claude-sonnet-4-6",
)


_CANNED_PROPOSE_CAUTION = FakeLLMResponse(
    parsed={
        "choice": "ProposeCaution",
        "confidence": 0.72,
        "confidence_band": "medium",
        "reasoning": (
            "Run aborted with hardware-vocabulary reason; signals a real "
            "operator-actionable pattern: the encoder went offline after "
            "12 minutes of continuous rotation."
        ),
        "proposed_caution": {
            "target_kind": "Asset",
            "target_id": str(_ASSET_ID),
            "category": "Wear",
            "severity": "Caution",
            "title": "Encoder drift after extended rotation",
            "body": (
                "Re-home the rotary stage encoder every 10 minutes of "
                "continuous rotation; drift accumulates and triggers "
                "interlock at ~12 minutes."
            ),
            "tags": ["encoder", "rotary-stage", "rotation"],
        },
    },
    stop_reason="tool_use",
    model_id="claude-sonnet-4-6",
)


# ---------------------------------------------------------------------------
# Subscriber metadata
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_subscriber_name_and_subscribed_event_types_pinned() -> None:
    """Name + event types are stable bytes (bookmark row keyed on name)."""
    subscriber = CautionDrafterSubscriber(
        event_store=InMemoryEventStore(),
        llm=FakeLLM(),
        caution_lookup=AlwaysQuietCautionLookup(),
    )
    assert subscriber.name == "caution_drafter"
    assert subscriber.subscribed_event_types == frozenset(
        {"RunCompleted", "RunAborted", "RunStopped", "RunTruncated"}
    )


@pytest.mark.unit
def test_subscriber_namespace_distinct_from_run_debriefer() -> None:
    """Decision-id namespaces must not collide between agents."""
    from cora.agent.subscribers.caution_drafter import (
        _CAUTION_DRAFTER_DECISION_NAMESPACE,
    )
    from cora.agent.subscribers.run_debriefer import _RUN_DEBRIEF_DECISION_NAMESPACE

    assert _CAUTION_DRAFTER_DECISION_NAMESPACE != _RUN_DEBRIEF_DECISION_NAMESPACE


# ---------------------------------------------------------------------------
# Happy path: ProposeCaution
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_apply_emits_caution_proposal_decision_on_run_aborted() -> None:
    """The load-bearing happy path: terminal Run -> Decision with full payload."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_PROPOSE_CAUTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(
        event_type="RunAborted",
        run_id=run_id,
        reason="rotary stage encoder offline; interlock fired",
    )

    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.context.value == "CautionProposal"
    assert decision.choice.value == "ProposeCaution"
    assert decision.confidence == pytest.approx(0.72)
    assert decision.actor_id == CAUTION_DRAFTER_AGENT_ID
    assert decision.rule is not None
    assert decision.rule.value == "agent:CautionDrafter:v1"
    # The proposed_caution tuple round-trips through inputs.
    assert decision.inputs is not None
    proposed = decision.inputs["proposed_caution"]
    assert proposed["target_kind"] == "Asset"
    assert proposed["target_id"] == str(_ASSET_ID)
    assert proposed["category"] == "Wear"
    assert proposed["severity"] == "Caution"
    assert proposed["title"].startswith("Encoder drift")
    # informed_by_decision_id is always None at v1.
    assert decision.inputs["informed_by_decision_id"] is None
    # confidence_band carried through always.
    assert decision.inputs["confidence_band"] == "medium"


# ---------------------------------------------------------------------------
# NoAction path (the most common outcome per design)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_apply_writes_no_action_decision() -> None:
    """The LLM refuses → Decision still written with no proposed_caution.

    Preserves the exactly-one-Decision-per-terminal-Run audit
    invariant + emits the telemetry signal for refuse-rate tracking.
    """
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_NO_ACTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    assert decision.choice.value == "NoAction"
    assert decision.confidence == pytest.approx(0.85)
    assert decision.inputs is not None
    # NoAction MUST NOT carry a proposed_caution payload.
    assert "proposed_caution" not in decision.inputs


# ---------------------------------------------------------------------------
# NoAction fallback on LLM exhaust (parallel to DebriefDeferred)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_apply_writes_no_action_deferred_on_llm_failure() -> None:
    """LLM raises → NoAction Decision with failure_error_class marker.

    Preserves exactly-one-Decision-per-Run invariant + lets operator
    re-trigger when re-draft slice ships.
    """
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[LLMServerError("synthetic 500")])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    assert decision.choice.value == "NoAction"
    assert decision.confidence is None
    assert "LLM call failed with LLMServerError" in (decision.reasoning or "")
    assert decision.inputs is not None
    assert decision.inputs["failure_error_class"] == "LLMServerError"


# ---------------------------------------------------------------------------
# Schema-violation fallback (proposed_caution missing on Propose* choice)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_apply_writes_no_action_deferred_when_proposed_caution_missing() -> None:
    """A Propose* choice WITHOUT proposed_caution payload is a schema
    violation; the subscriber falls back to NoAction-deferred."""
    bad_response = FakeLLMResponse(
        parsed={
            "choice": "ProposeNotice",
            "confidence": 0.7,
            "confidence_band": "medium",
            "reasoning": "missing proposed_caution despite Propose* choice",
            # proposed_caution intentionally absent
        },
        stop_reason="tool_use",
        model_id="claude-sonnet-4-6",
    )
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[bad_response])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    assert decision.choice.value == "NoAction"
    assert decision.inputs is not None
    assert decision.inputs["failure_error_class"] == "SchemaViolation"


@pytest.mark.unit
async def test_apply_writes_no_action_deferred_when_target_id_not_in_candidates() -> None:
    """LLM returns a UUID NOT present in `candidate_targets` (Plan.asset_ids).

    The output-schema enum was meant to constrain this, but a
    misconfigured / poisoned LLM can emit arbitrary UUIDs. The
    subscriber re-validates membership and falls back to
    NoAction-deferred with `failure_error_class=HallucinatedTarget`,
    so the Decision is never written against an unknown target.
    """
    rogue_target_id = uuid4()
    assert rogue_target_id != _ASSET_ID, "test fixture must use a fresh UUID"
    hallucinated = FakeLLMResponse(
        parsed={
            "choice": "ProposeCaution",
            "confidence": 0.7,
            "confidence_band": "medium",
            "reasoning": (
                "Plausible reasoning narrative for the proposed Caution, "
                "but the target_id below is fabricated / not in the prompt's "
                "candidate_targets list."
            ),
            "proposed_caution": {
                "target_kind": "Asset",
                "target_id": str(rogue_target_id),
                "category": "Wear",
                "severity": "Caution",
                "title": "Hallucinated target Caution",
                "body": "Body for the hallucinated-target Caution.",
                "tags": [],
            },
        },
        stop_reason="tool_use",
        model_id="claude-sonnet-4-6",
    )
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[hallucinated])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    assert decision.choice.value == "NoAction"
    assert decision.inputs is not None
    assert decision.inputs["failure_error_class"] == "HallucinatedTarget"
    # The hallucinated proposed_caution must NOT have been persisted; the
    # NoAction-deferred path emits a minimal inputs dict with no
    # proposed_caution field.
    assert "proposed_caution" not in decision.inputs


# ---------------------------------------------------------------------------
# At-most-once: deterministic decision_id + ConcurrencyError as no-op
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_apply_is_at_most_once_via_deterministic_decision_id() -> None:
    """Two applies with the same terminal_event_id produce ONE Decision.

    Second apply hits ConcurrencyError on expected_version=0 and the
    subscriber's catch treats it as success.
    """
    store = InMemoryEventStore()
    llm1 = FakeLLM(responses=[_CANNED_PROPOSE_CAUTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm1)
    event = _terminal_event(
        event_type="RunAborted",
        run_id=run_id,
        reason="encoder offline",
    )

    await subscriber.apply(event, conn=None)
    # Second apply, fresh LLM (would produce different output) - but
    # ConcurrencyError catch should prevent any new write.
    llm2 = FakeLLM(responses=[_CANNED_NO_ACTION])
    subscriber2 = await _build_subscriber(store, llm2)
    await subscriber2.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is not None
    # The FIRST decision (ProposeCaution) wins; second attempt is a no-op.
    assert decision.choice.value == "ProposeCaution"


# ---------------------------------------------------------------------------
# Skip guards
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_apply_skips_when_plan_missing() -> None:
    """No Plan -> subscriber logs warning and returns without writing.

    The Plan-load guard is CautionDrafter-specific (RunDebriefer
    doesn't load Plan). Without it the subscriber would crash on
    `plan.asset_ids`.
    """
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_PROPOSE_CAUTION])
    await _seed_caution_drafter_actor(store)
    # Intentionally NO _seed_plan() call.
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is None
    # LLM should never have been called (skip happens before chat).
    assert llm.received == []


@pytest.mark.unit
async def test_apply_skips_when_agent_actor_missing() -> None:
    """No CautionDrafter Actor seeded -> skip without writing."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_PROPOSE_CAUTION])
    await _seed_plan(store)
    # Intentionally NO _seed_caution_drafter_actor() call.
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is None
    assert llm.received == []


@pytest.mark.unit
async def test_apply_skips_when_agent_actor_deactivated() -> None:
    """Operator-revocation gate: deactivated Actor must not author Decisions."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_PROPOSE_CAUTION])
    await _seed_caution_drafter_actor(store, deactivated=True)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is None
    assert llm.received == []


# ---------------------------------------------------------------------------
# Defensive: non-terminal event filter
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_apply_ignores_non_terminal_event_defensively() -> None:
    """Worker already filters by subscribed_event_types; defensive check."""
    store = InMemoryEventStore()
    llm = FakeLLM()
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    subscriber = await _build_subscriber(store, llm)
    # RunStarted is NOT in subscribed_event_types.
    not_terminal = StoredEvent(
        position=1,
        event_id=UUID("01900000-0000-7000-8000-00000000ff02"),
        stream_type="Run",
        stream_id=run_id,
        version=1,
        event_type="RunStarted",
        schema_version=1,
        payload={"run_id": str(run_id)},
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_LATER,
        recorded_at=_LATER,
    )

    await subscriber.apply(not_terminal, conn=None)

    assert llm.received == []


@pytest.mark.unit
async def test_apply_skips_when_run_missing() -> None:
    """No Run aggregate in the store -> skip without writing.

    Mirrors the Plan/Actor skip guards. The Run-load guard sits before
    Plan/Actor in the apply() body so it short-circuits the earliest.
    """
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_PROPOSE_CAUTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    # Intentionally NO _seed_run() call.
    subscriber = await _build_subscriber(store, llm)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    await subscriber.apply(event, conn=None)

    decision = await load_decision(store, _derive_decision_id(event.event_id))
    assert decision is None
    assert llm.received == []


# ---------------------------------------------------------------------------
# LLM-output sanitization helpers (poisoned-LLM defensive returns)
#
# `_proposed_target_in_candidates` and `_coerce_proposed_caution` are the
# trust-boundary between LLM output and CORA's domain. Both treat the
# parsed dict as adversarial — the structured-output schema constrains
# shape but a misconfigured / poisoned LLM can emit arbitrary values.
# The hallucinated-target case is covered upstream by the subscriber-
# level test; these tests pin the lower-level defensive returns.
# ---------------------------------------------------------------------------


_VALID_TARGETS = frozenset({_ASSET_ID})


@pytest.mark.unit
def test_proposed_target_in_candidates_returns_false_for_non_dict() -> None:
    assert _proposed_target_in_candidates("not-a-dict", _VALID_TARGETS) is False
    assert _proposed_target_in_candidates(None, _VALID_TARGETS) is False
    assert _proposed_target_in_candidates(["a", "list"], _VALID_TARGETS) is False


@pytest.mark.unit
def test_proposed_target_in_candidates_returns_false_for_non_string_target_id() -> None:
    """LLM emits target_id as an int / None / nested object instead of UUID-string."""
    assert _proposed_target_in_candidates({"target_id": 12345}, _VALID_TARGETS) is False
    assert _proposed_target_in_candidates({"target_id": None}, _VALID_TARGETS) is False
    assert _proposed_target_in_candidates({"target_id": {"nested": "x"}}, _VALID_TARGETS) is False
    assert _proposed_target_in_candidates({}, _VALID_TARGETS) is False  # key missing


@pytest.mark.unit
def test_proposed_target_in_candidates_returns_false_for_unparseable_uuid() -> None:
    """target_id is a string but not a well-formed UUID."""
    assert _proposed_target_in_candidates({"target_id": "not-a-uuid"}, _VALID_TARGETS) is False
    assert _proposed_target_in_candidates({"target_id": ""}, _VALID_TARGETS) is False


@pytest.mark.unit
def test_proposed_target_in_candidates_returns_true_for_valid_uuid_in_set() -> None:
    """Pin the True path so the test parity holds with the False arms."""
    assert _proposed_target_in_candidates({"target_id": str(_ASSET_ID)}, _VALID_TARGETS) is True


@pytest.mark.unit
def test_coerce_proposed_caution_raises_on_non_dict() -> None:
    """Defensive: a Propose* choice whose proposed_caution is somehow not
    a dict (schema violation that the membership check upstream didn't
    catch — for example, LLM returned a list) must raise rather than silently
    coerce garbage into the Decision payload."""
    with pytest.raises(ValueError, match="must be a dict"):
        _coerce_proposed_caution(["not", "a", "dict"])
    with pytest.raises(ValueError, match="must be a dict"):
        _coerce_proposed_caution(None)


@pytest.mark.unit
def test_coerce_proposed_caution_carries_supersedes_caution_id_when_present() -> None:
    """`ProposeSupersede` choice carries `supersedes_caution_id` in the
    proposed_caution payload; the coercer must preserve it as a string
    for byte-stable round-trip. The base path (no supersedes_caution_id)
    is exercised by every existing happy-path test."""
    parent_caution_id = uuid4()
    coerced = _coerce_proposed_caution(
        {
            "target_kind": "Asset",
            "target_id": str(_ASSET_ID),
            "category": "Wear",
            "severity": "Warning",
            "title": "Updated guidance after re-investigation",
            "body": "Re-home encoder every 5 minutes; the 10-minute interval was insufficient.",
            "tags": ["encoder"],
            "supersedes_caution_id": str(parent_caution_id),
        }
    )
    assert coerced["supersedes_caution_id"] == str(parent_caution_id)
    assert coerced["target_kind"] == "Asset"


# ---------------------------------------------------------------------------
# Factory guard
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_make_caution_drafter_subscriber_raises_when_llm_is_none() -> None:
    """The subscriber is useless without an LLM. The conditional-
    registration shim in `cora.agent._subscribers.register_agent_subscribers`
    is supposed to short-circuit on `llm is None`, so this fail-fast
    only fires for misconfigured callers that bypass that shim."""
    deps = build_deps(llm=None)
    with pytest.raises(RuntimeError, match=r"requires kernel\.llm"):
        make_caution_drafter_subscriber(deps)


@pytest.mark.unit
def test_make_caution_drafter_subscriber_constructs_when_llm_is_set() -> None:
    """Pin the success branch — factory wires through to the subscriber
    instance when the Kernel has an LLM port configured."""
    deps = build_deps(llm=FakeLLM())
    subscriber = make_caution_drafter_subscriber(deps)
    assert isinstance(subscriber, CautionDrafterSubscriber)


# ---------- Signer wiring ----------


@pytest.mark.unit
async def test_apply_leaves_signature_none_when_no_signer_configured() -> None:
    """Backward-compat: subscriber without a Signer dep produces
    unsigned events. Default for every existing deployment."""
    from cora.infrastructure.ports.event_store import StoredEvent

    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_NO_ACTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
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
    llm = FakeLLM(responses=[_CANNED_NO_ACTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    signer = Ed25519FakeSigner(kid="kid-caution-drafter")
    subscriber = CautionDrafterSubscriber(
        event_store=store,
        llm=llm,
        caution_lookup=AlwaysQuietCautionLookup(),
        signer=signer,
    )
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)
    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    events, _ = await store.load("Decision", decision_id)
    stored: StoredEvent = events[0]
    assert stored.signature is not None
    assert stored.signature_kid == "kid-caution-drafter"
    assert len(stored.signature) == 64
    # The subscriber MUST pass the Agent's id to the signer; a regression
    # that dropped or renamed the `actor_id` kwarg would silently sign
    # with the wrong identity in production.
    assert signer.received_actor_ids == [CAUTION_DRAFTER_AGENT_ID]

    async def _resolver(kid: str) -> bytes:
        assert kid == "kid-caution-drafter"
        return signer.public_key_bytes

    # Re-verify against the stored bytes; raises SignatureInvalidError on
    # failure. Round-trip proves the canonicalization profile sign-side
    # matches the verify-side.
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
    Sibling of the same helper in `test_run_debriefer_subscriber.py`;
    kept local because the two subscriber test modules already
    duplicate their seed scaffolding and the helper is only three
    lines."""

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
    """Symmetric to the RunDebriefer fail-closed test: when the Signer
    raises any documented error, the CautionDrafter subscriber MUST
    propagate it and MUST NOT persist an unsigned `DecisionRegistered`.
    Both agent subscribers share the `_maybe_sign` shape and the
    same fail-closed invariant from the Candidate F design lock."""
    from cora.infrastructure.ports.signer import (
        SignerKeyInactiveError,
        SignerKeyNotFoundError,
        SignerUnavailableError,
    )

    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_NO_ACTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)

    exc: Exception
    if failure == "unavailable":
        exc = SignerUnavailableError("sigstore-fulcio", detail="connection refused")
    elif failure == "inactive_key":
        exc = SignerKeyInactiveError("kid-caution-drafter-old")
    else:
        exc = SignerKeyNotFoundError(CAUTION_DRAFTER_AGENT_ID)

    subscriber = CautionDrafterSubscriber(
        event_store=store,
        llm=llm,
        caution_lookup=AlwaysQuietCautionLookup(),
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
    transport error not yet wrapped in `SignerUnavailableError`) MUST
    propagate, locking the absence of a bare `except Exception` around
    the signing call."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_NO_ACTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)

    subscriber = CautionDrafterSubscriber(
        event_store=store,
        llm=llm,
        caution_lookup=AlwaysQuietCautionLookup(),
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
    Run stream BEFORE invoking the LLM. Mirrors RunDebriefer; the
    primitive's existence on the stream IS the lease."""
    from cora.agent._subscriber_lease import derive_lease_event_id

    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_NO_ACTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
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
    assert lease.payload["debriefer_agent_id"] == str(CAUTION_DRAFTER_AGENT_ID)
    assert lease.payload["terminal_event_id"] == str(event.event_id)
    assert lease.event_id == derive_lease_event_id(
        run_id=run_id,
        debriefer_agent_id=CAUTION_DRAFTER_AGENT_ID,
        terminal_event_id=event.event_id,
    )


@pytest.mark.unit
async def test_apply_writes_caution_draft_conflicted_when_another_agent_holds_lease() -> None:
    """When a different agent already holds the lease, the subscriber
    writes CautionDraftConflicted on its own Decision stream WITHOUT
    invoking the LLM. Losing agents pay zero LLM cost."""
    from cora.agent._subscriber_lease import attempt_debrief_lease

    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_NO_ACTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

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

    subscriber = await _build_subscriber(store, llm)
    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.context.value == "CautionProposal"
    assert decision.choice.value == "CautionDraftConflicted"
    assert decision.confidence is None
    assert decision.inputs is not None
    assert decision.inputs["winning_agent_id"] == str(foreign_agent_id)
    assert llm.received == []


@pytest.mark.unit
async def test_apply_writes_caution_draft_conflicted_unidentified_winner_on_no_winner_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`(False, None)` from the lease helper (degenerate-loss path
    where the Run stream advanced for a non-lease reason between
    load and append) lands a CautionDraftConflicted Decision whose
    reasoning notes the unidentified winner and whose `inputs` omits
    `winning_agent_id`. Mirrors RunDebriefer."""
    store = InMemoryEventStore()
    llm = FakeLLM(responses=[_CANNED_NO_ACTION])
    await _seed_caution_drafter_actor(store)
    await _seed_plan(store)
    run_id = uuid4()
    await _seed_run(store, run_id)
    event = _terminal_event(event_type="RunCompleted", run_id=run_id)

    async def _force_loss_without_winner(*_args: object, **_kwargs: object) -> tuple[bool, None]:
        return False, None

    monkeypatch.setattr(
        "cora.agent.subscribers.caution_drafter.attempt_debrief_lease",
        _force_loss_without_winner,
    )

    subscriber = await _build_subscriber(store, llm)
    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(store, decision_id)
    assert decision is not None
    assert decision.choice.value == "CautionDraftConflicted"
    assert decision.confidence is None
    assert decision.inputs is not None
    assert "winning_agent_id" not in decision.inputs
    assert decision.reasoning is not None
    assert "winning agent not identified" in decision.reasoning
    assert llm.received == []
