"""Tests for the ExperimentSteerer Decision seam (cora.api._experiment_steerer).

Covers the across-procedure steering-Decision write: the signed agent-write path
(an Agent cannot use register_decision), the AdviceAuditFields -> Decision
provenance mapping (shared with the iteration ledger), deterministic-id
idempotency, the stand-down guard (unseeded / deactivated agent), and the
decided_by_decision_id linkage that lets the recorded Decision justify a follow-on
agent-issued hold_procedure.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.seed_experiment_steerer import (
    EXPERIMENT_STEERER_AGENT_ID,
    seed_experiment_steerer_agent,
)
from cora.api._experiment_steerer import _derive_decision_id, record_steering_decision
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_EXPERIMENT_STEERING,
    DecisionConfidenceSource,
    load_decision,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.signing import verify_signature
from cora.operation.ports.decide_port import AdviceAuditFields
from tests.unit.agent._helpers import Ed25519FakeSigner

_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)


def _kernel(*, signer: Ed25519FakeSigner | None = None) -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
        signer=signer,
    )


def _audit(
    *,
    reasoning: str | None = "objective met across two procedures",
    confidence: float | None = 0.8,
    confidence_source: DecisionConfidenceSource | None = DecisionConfidenceSource.SELF_REPORTED,
    alternatives: tuple[str, ...] = ("Continue",),
    model_ref: str | None = "grid_walk",
) -> AdviceAuditFields:
    return AdviceAuditFields(
        reasoning=reasoning,
        confidence=confidence,
        confidence_source=confidence_source,
        alternatives=alternatives,
        model_ref=model_ref,
    )


@pytest.mark.unit
async def test_record_steering_decision_writes_experiment_steering_decision() -> None:
    """One Decision(context=ExperimentSteering) is written, authored by the agent."""
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)
    procedure_id = uuid4()

    decision_id = await record_steering_decision(
        kernel,
        procedure_id=procedure_id,
        turn=0,
        choice="Conclude",
        advice_audit=_audit(),
    )

    assert decision_id is not None
    decision = await load_decision(kernel.event_store, decision_id)
    assert decision is not None
    assert decision.context.value == DECISION_CONTEXT_EXPERIMENT_STEERING
    assert decision.choice.value == "Conclude"
    assert decision.decided_by == EXPERIMENT_STEERER_AGENT_ID
    assert decision.rule is not None
    assert decision.rule.value == "agent:ExperimentSteerer:v1"


@pytest.mark.unit
async def test_record_steering_decision_maps_advice_audit_fields() -> None:
    """The AdviceAuditFields land on the Decision provenance (shared mapping)."""
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)
    procedure_id = uuid4()

    decision_id = await record_steering_decision(
        kernel,
        procedure_id=procedure_id,
        turn=0,
        choice="Continue",
        advice_audit=_audit(
            reasoning="one more procedure should hit the target",
            confidence=0.6,
            confidence_source=DecisionConfidenceSource.LOGPROB,
            alternatives=("Conclude",),
            model_ref="grid_walk",
        ),
    )

    assert decision_id is not None
    decision = await load_decision(kernel.event_store, decision_id)
    assert decision is not None
    assert decision.reasoning == "one more procedure should hit the target"
    assert decision.confidence == pytest.approx(0.6)
    assert decision.confidence_source is DecisionConfidenceSource.LOGPROB
    assert decision.alternatives == ("Conclude",)
    assert decision.inputs is not None
    assert decision.inputs["procedure_id"] == str(procedure_id)
    assert decision.inputs["turn"] == 0
    assert decision.inputs["model_ref"] == "grid_walk"


@pytest.mark.unit
async def test_record_steering_decision_signs_when_signer_configured() -> None:
    """The agent-authored DecisionRegistered is signed (AI-agent rows are signed)."""
    signer = Ed25519FakeSigner(kid="kid-experiment-steerer")
    kernel = _kernel(signer=signer)
    await seed_experiment_steerer_agent(kernel)
    procedure_id = uuid4()

    decision_id = await record_steering_decision(
        kernel,
        procedure_id=procedure_id,
        turn=0,
        choice="Conclude",
        advice_audit=_audit(),
    )

    assert decision_id is not None
    events, _ = await kernel.event_store.load("Decision", decision_id)
    stored = events[0]
    assert stored.signature is not None
    assert stored.signature_kid == "kid-experiment-steerer"
    assert len(stored.signature) == 64
    # The seam MUST sign as the agent's id (a dropped actor_id would sign with the
    # wrong identity in production but pass without this lock).
    assert signer.received_actor_ids == [EXPERIMENT_STEERER_AGENT_ID]

    async def _resolver(kid: str) -> bytes:
        assert kid == "kid-experiment-steerer"
        return signer.public_key_bytes

    await verify_signature(
        event_type=stored.event_type,
        payload=stored.payload,
        signature=stored.signature,
        kid=stored.signature_kid,
        resolve_public_key=_resolver,
    )


@pytest.mark.unit
async def test_record_steering_decision_deterministic_id_idempotent() -> None:
    """A retried record (same procedure + turn) is a no-op, not a duplicate."""
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)
    procedure_id = uuid4()

    first = await record_steering_decision(
        kernel, procedure_id=procedure_id, turn=0, choice="Continue", advice_audit=_audit()
    )
    second = await record_steering_decision(
        kernel, procedure_id=procedure_id, turn=0, choice="Continue", advice_audit=_audit()
    )

    assert first is not None
    assert first == second
    assert first == _derive_decision_id(procedure_id, 0)
    events, _ = await kernel.event_store.load("Decision", first)
    assert len(events) == 1


@pytest.mark.unit
async def test_record_steering_decision_distinct_turns_distinct_decisions() -> None:
    """Each across-procedure turn derives its own Decision id."""
    kernel = _kernel()
    await seed_experiment_steerer_agent(kernel)
    procedure_id = uuid4()

    turn0 = await record_steering_decision(
        kernel, procedure_id=procedure_id, turn=0, choice="Continue", advice_audit=_audit()
    )
    turn1 = await record_steering_decision(
        kernel, procedure_id=procedure_id, turn=1, choice="Conclude", advice_audit=_audit()
    )

    assert turn0 is not None
    assert turn1 is not None
    assert turn0 != turn1


@pytest.mark.unit
async def test_record_steering_decision_stands_down_when_agent_unseeded() -> None:
    """No seeded agent -> stand down (None), no Decision written, no bypass."""
    kernel = _kernel()  # ExperimentSteerer NOT seeded
    procedure_id = uuid4()

    decision_id = await record_steering_decision(
        kernel, procedure_id=procedure_id, turn=0, choice="Conclude", advice_audit=_audit()
    )

    assert decision_id is None
    events, _ = await kernel.event_store.load("Decision", _derive_decision_id(procedure_id, 0))
    assert events == []


@pytest.mark.unit
async def test_steering_decision_links_a_follow_on_procedure_hold() -> None:
    """The recorded Decision id threads into an agent-issued hold_procedure.

    Proves the across-procedure primitive: the steerer records a Hold disposition,
    then issues hold_procedure carrying decided_by_decision_id, and ProcedureHeld
    persists that link.
    """
    from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
    from cora.operation.aggregates.procedure import load_procedure
    from cora.operation.features.hold_procedure import HoldProcedure
    from cora.operation.features.hold_procedure import bind as bind_hold_procedure
    from tests.unit.operation._helpers import seed_running_procedure

    kernel = _kernel()
    assert isinstance(kernel.event_store, InMemoryEventStore)
    store = kernel.event_store
    await seed_experiment_steerer_agent(kernel)
    procedure_id = uuid4()
    correlation_id = uuid4()
    await seed_running_procedure(
        store,
        procedure_id=procedure_id,
        when=_NOW,
        correlation_id=correlation_id,
        principal_id=EXPERIMENT_STEERER_AGENT_ID,
    )

    decision_id = await record_steering_decision(
        kernel, procedure_id=procedure_id, turn=0, choice="Hold", advice_audit=_audit()
    )
    assert decision_id is not None

    await bind_hold_procedure(kernel)(
        HoldProcedure(
            procedure_id=procedure_id,
            reason="ExperimentSteerer paused the campaign between procedures",
            decided_by_decision_id=decision_id,
        ),
        principal_id=EXPERIMENT_STEERER_AGENT_ID,
        correlation_id=correlation_id,
    )

    procedure = await load_procedure(kernel.event_store, procedure_id)
    assert procedure is not None
    assert procedure.status.value == "Held"
    events, _ = await kernel.event_store.load("Procedure", procedure_id)
    held = next(e for e in events if e.event_type == "ProcedureHeld")
    assert held.payload["decided_by_decision_id"] == str(decision_id)
