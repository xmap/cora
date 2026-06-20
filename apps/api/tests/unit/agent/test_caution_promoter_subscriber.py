"""Tests for the CautionPromoter subscriber.

Covers the pure gate (decide-disposition across every branch via _evaluate) and
the end-to-end apply path (Promote writes a Decision + a live Caution with
deterministic ids; idempotent re-delivery; provenance / context / Actor.active
skips).
"""

# white-box test of the subscriber internals (private helpers / gate)
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.features.promote_caution_proposal.decider import ProposedCautionView
from cora.agent.seed_caution_drafter import CAUTION_DRAFTER_AGENT_ID, seed_caution_drafter_agent
from cora.agent.seed_caution_promoter import (
    CAUTION_PROMOTER_AGENT_ID,
    seed_caution_promoter_agent,
)
from cora.agent.subscribers.caution_promoter import (
    CautionPromoterSubscriber,
    _build_target,
    _derive_caution_id,
    _derive_decision_id,
    make_caution_promoter_subscriber,
)
from cora.caution.aggregates.caution import load_caution
from cora.decision.aggregates.decision import (
    Decision,
    DecisionConfidenceSource,
    DecisionRegistered,
    event_type_name,
    load_decision,
    to_payload,
)
from cora.decision.aggregates.decision.evolver import fold
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    Authorize,
    Deny,
    FakeClock,
    UUIDv7Generator,
)
from cora.infrastructure.ports.caution_lookup import CautionLookupResult
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


class _FakeLookup:
    def __init__(self, results: list[CautionLookupResult]) -> None:
        self._results = results

    async def find_active_for_run(
        self,
        *,
        asset_ids: frozenset[UUID],
        procedure_ids: frozenset[UUID],
        min_severity: str = "Caution",
    ) -> list[CautionLookupResult]:
        _ = (asset_ids, procedure_ids, min_severity)
        return self._results


class _DenyAll:
    async def authorize(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Deny:
        _ = (principal_id, command_name, conduit_id, surface_id)
        return Deny("not permitted")


def _view(
    *, choice: str = "ProposeNotice", severity: str = "Notice", target_kind: str = "Asset"
) -> ProposedCautionView:
    return ProposedCautionView(
        decision_id=uuid4(),
        choice=choice,
        target_kind=target_kind,
        target_id=uuid4(),
        category="OperationalWindow",
        severity=severity,
        title="Top-up flux transients",
        body="Brief flux dips during top-up injection; allow the scan to settle.",
        tags=(),
        supersedes_caution_id=None,
    )


def _decision(*, confidence: float | None) -> Decision:
    event = DecisionRegistered(
        decision_id=uuid4(),
        decided_by=ActorId(CAUTION_DRAFTER_AGENT_ID),
        context="CautionProposal",
        choice="ProposeNotice",
        parent_id=None,
        override_kind=None,
        rule="agent:CautionDrafter:v1",
        reasoning="proposed",
        confidence=confidence,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        inputs=None,
        reasoning_signature=None,
        occurred_at=_NOW,
    )
    decision = fold([event])
    assert decision is not None
    return decision


def _sub(
    kernel: Kernel, *, authz: Authorize | None = None, lookup: _FakeLookup | None = None
) -> CautionPromoterSubscriber:
    return CautionPromoterSubscriber(
        event_store=kernel.event_store,
        authz=authz or AllowAllAuthorize(),
        caution_lookup=lookup or _FakeLookup([]),
        clock=kernel.clock,
        id_generator=kernel.id_generator,
    )


def _conflict_result() -> CautionLookupResult:
    return CautionLookupResult(
        caution_id=uuid4(),
        target_kind="Asset",
        target_id=uuid4(),
        category="OperationalWindow",
        severity="Notice",
        text_excerpt="existing",
        workaround_excerpt="existing",
    )


# ---------- gate: _evaluate ----------


@pytest.mark.unit
async def test_gate_promotes_high_confidence_notice_with_no_conflict() -> None:
    out, _ = await _sub(_kernel())._evaluate(_view(), _decision(confidence=0.9))
    assert out == "Promote"


@pytest.mark.unit
async def test_gate_defers_above_notice() -> None:
    out, _ = await _sub(_kernel())._evaluate(
        _view(choice="ProposeCaution", severity="Caution"), _decision(confidence=0.99)
    )
    assert out == "PromotionDeferred"


@pytest.mark.unit
async def test_gate_defers_low_confidence() -> None:
    out, _ = await _sub(_kernel())._evaluate(_view(), _decision(confidence=0.3))
    assert out == "PromotionDeferred"


@pytest.mark.unit
async def test_gate_defers_missing_confidence() -> None:
    out, _ = await _sub(_kernel())._evaluate(_view(), _decision(confidence=None))
    assert out == "PromotionDeferred"


@pytest.mark.unit
async def test_gate_conflicts_when_active_caution_on_target() -> None:
    sub = _sub(_kernel(), lookup=_FakeLookup([_conflict_result()]))
    out, _ = await sub._evaluate(_view(), _decision(confidence=0.9))
    assert out == "PromotionConflicted"


@pytest.mark.unit
async def test_gate_defers_when_authorize_denies() -> None:
    sub = _sub(_kernel(), authz=_DenyAll())
    out, _ = await sub._evaluate(_view(), _decision(confidence=0.9))
    assert out == "PromotionDeferred"


# ---------- apply: end to end ----------


async def _write_proposal(
    kernel: Kernel,
    *,
    decided_by: UUID = CAUTION_DRAFTER_AGENT_ID,
    choice: str = "ProposeNotice",
    severity: str = "Notice",
    confidence: float = 0.9,
) -> tuple[UUID, StoredEvent]:
    proposal_id = uuid4()
    proposed: dict[str, object] = {
        "target_kind": "Asset",
        "target_id": str(uuid4()),
        "category": "OperationalWindow",
        "severity": severity,
        "title": "Top-up flux transients",
        "body": "Brief flux dips during top-up injection; allow the scan to settle.",
        "tags": [],
    }
    domain = DecisionRegistered(
        decision_id=proposal_id,
        decided_by=ActorId(decided_by),
        context="CautionProposal",
        choice=choice,
        parent_id=None,
        override_kind=None,
        rule="agent:CautionDrafter:v1",
        reasoning="proposed",
        confidence=confidence,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        inputs={"proposed_caution": proposed},
        reasoning_signature=None,
        occurred_at=_NOW,
    )
    payload = to_payload(domain)
    await kernel.event_store.append(
        stream_type="Decision",
        stream_id=proposal_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(domain),
                payload=payload,
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="CautionDrafterSubscriber",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=decided_by,
            )
        ],
    )
    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Decision",
        stream_id=proposal_id,
        version=1,
        event_type="DecisionRegistered",
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )
    return proposal_id, stored


@pytest.mark.unit
async def test_apply_promotes_and_writes_decision_and_caution() -> None:
    kernel = _kernel()
    await seed_caution_drafter_agent(kernel)
    await seed_caution_promoter_agent(kernel)
    proposal_id, stored = await _write_proposal(kernel)
    sub = _sub(kernel)

    await sub.apply(stored, None)  # type: ignore[arg-type]

    promo = await load_decision(kernel.event_store, _derive_decision_id(proposal_id))
    assert promo is not None
    assert promo.context.value == "CautionPromotion"
    assert promo.choice.value == "Promote"
    assert promo.parent_id == proposal_id
    assert promo.decided_by == ActorId(CAUTION_PROMOTER_AGENT_ID)

    caution = await load_caution(kernel.event_store, _derive_caution_id(proposal_id))
    assert caution is not None
    assert caution.severity.value == "Notice"
    assert caution.authored_by == ActorId(CAUTION_PROMOTER_AGENT_ID)


@pytest.mark.unit
async def test_apply_is_idempotent_on_redelivery() -> None:
    kernel = _kernel()
    await seed_caution_drafter_agent(kernel)
    await seed_caution_promoter_agent(kernel)
    proposal_id, stored = await _write_proposal(kernel)
    sub = _sub(kernel)

    await sub.apply(stored, None)  # type: ignore[arg-type]
    await sub.apply(stored, None)  # type: ignore[arg-type]

    # Re-delivery is a no-op; the Caution still exists exactly once.
    caution = await load_caution(kernel.event_store, _derive_caution_id(proposal_id))
    assert caution is not None


@pytest.mark.unit
async def test_apply_defers_above_notice_writes_no_caution() -> None:
    kernel = _kernel()
    await seed_caution_drafter_agent(kernel)
    await seed_caution_promoter_agent(kernel)
    proposal_id, stored = await _write_proposal(kernel, choice="ProposeWarning", severity="Warning")
    sub = _sub(kernel)

    await sub.apply(stored, None)  # type: ignore[arg-type]

    promo = await load_decision(kernel.event_store, _derive_decision_id(proposal_id))
    assert promo is not None
    assert promo.choice.value == "PromotionDeferred"
    assert await load_caution(kernel.event_store, _derive_caution_id(proposal_id)) is None


@pytest.mark.unit
async def test_apply_skips_non_caution_proposal_context() -> None:
    kernel = _kernel()
    await seed_caution_promoter_agent(kernel)
    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Decision",
        stream_id=uuid4(),
        version=1,
        event_type="DecisionRegistered",
        schema_version=1,
        payload={"context": "RunDebrief", "decision_id": str(uuid4())},
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )
    # No exception, no work.
    await _sub(kernel).apply(stored, None)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_apply_skips_proposal_from_non_caution_drafter_author() -> None:
    kernel = _kernel()
    await seed_caution_promoter_agent(kernel)
    # decided_by is a random actor, not a registered CautionDrafter agent.
    proposal_id, stored = await _write_proposal(kernel, decided_by=uuid4())
    sub = _sub(kernel)

    await sub.apply(stored, None)  # type: ignore[arg-type]

    assert await load_decision(kernel.event_store, _derive_decision_id(proposal_id)) is None


@pytest.mark.unit
async def test_apply_skips_when_promoter_actor_absent() -> None:
    kernel = _kernel()  # CautionPromoter NOT seeded
    await seed_caution_drafter_agent(kernel)
    proposal_id, stored = await _write_proposal(kernel)
    sub = _sub(kernel)

    await sub.apply(stored, None)  # type: ignore[arg-type]

    assert await load_decision(kernel.event_store, _derive_decision_id(proposal_id)) is None


@pytest.mark.unit
def test_make_subscriber_from_kernel_builds_reaction() -> None:
    sub = make_caution_promoter_subscriber(_kernel())
    assert sub.name == "caution_promoter"
    assert sub.subscribed_event_types == frozenset({"DecisionRegistered"})
    assert sub.batch_size == 1


@pytest.mark.unit
async def test_gate_handles_procedure_target() -> None:
    out, _ = await _sub(_kernel())._evaluate(
        _view(target_kind="Procedure"), _decision(confidence=0.9)
    )
    assert out == "Promote"


@pytest.mark.unit
async def test_gate_returns_deferred_on_invalid_caution_fields() -> None:
    """Choice is Notice but the proposed severity is invalid: defer, never raise."""
    out, _ = await _sub(_kernel())._evaluate(
        _view(severity="NotARealSeverity"), _decision(confidence=0.9)
    )
    assert out == "PromotionDeferred"


@pytest.mark.unit
def test_build_target_maps_kinds_and_rejects_unknown() -> None:
    from cora.caution.aggregates.caution import AssetTarget, ProcedureTarget

    assert isinstance(_build_target(_view(target_kind="Asset")), AssetTarget)
    assert isinstance(_build_target(_view(target_kind="Procedure")), ProcedureTarget)
    with pytest.raises(ValueError, match="target_kind"):
        _build_target(_view(target_kind="Galaxy"))


def _stored_decision_event(
    *, context: str, decision_id: UUID | None, event_type: str
) -> StoredEvent:
    payload: dict[str, object] = {"context": context}
    if decision_id is not None:
        payload["decision_id"] = str(decision_id)
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Decision",
        stream_id=decision_id or uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
async def test_apply_ignores_non_decision_registered_event() -> None:
    stored = _stored_decision_event(
        context="CautionProposal", decision_id=uuid4(), event_type="RunStarted"
    )
    await _sub(_kernel()).apply(stored, None)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_apply_swallows_malformed_proposal_event() -> None:
    """Context passes the filter but decision_id is missing: swallow, do not wedge."""
    kernel = _kernel()
    await seed_caution_promoter_agent(kernel)
    stored = _stored_decision_event(
        context="CautionProposal", decision_id=None, event_type="DecisionRegistered"
    )
    await _sub(kernel).apply(stored, None)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_apply_skips_when_decision_not_in_store() -> None:
    kernel = _kernel()
    await seed_caution_promoter_agent(kernel)
    missing = uuid4()
    stored = _stored_decision_event(
        context="CautionProposal", decision_id=missing, event_type="DecisionRegistered"
    )
    await _sub(kernel).apply(stored, None)  # type: ignore[arg-type]
    assert await load_decision(kernel.event_store, _derive_decision_id(missing)) is None


@pytest.mark.unit
async def test_write_caution_is_idempotent_on_repeated_call() -> None:
    kernel = _kernel()
    sub = _sub(kernel)
    proposal_id = uuid4()
    view = _view()
    await sub._write_caution(view=view, proposal_id=proposal_id)
    await sub._write_caution(view=view, proposal_id=proposal_id)
    assert await load_caution(kernel.event_store, _derive_caution_id(proposal_id)) is not None
