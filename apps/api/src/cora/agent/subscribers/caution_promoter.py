"""Reaction: a CautionDrafter CautionProposal -> auto-promoted live Caution.

CautionPromoter is CORA's 2nd ACTIVE agent and the first hosted as an
event-triggered subscriber. It reacts to `DecisionRegistered`, filters to
`context=CautionProposal` Decisions authored by a registered CautionDrafter
agent, and applies a DETERMINISTIC gate. When the gate passes it writes a live
`CautionRegistered` directly to the Caution BC stream (Pattern C, the same
cross-BC write `promote_caution_proposal` performs), and it records one
`DecisionRegistered(context=CautionPromotion, parent_id=<proposal>)` per
proposal.

Precedent is split: CautionDrafter provides the subscriber HOST shape (it writes
only Decisions, never Cautions); `promote_caution_proposal` provides the
Caution-WRITE shape + the proposal-view decider + the VO validation. This is the
first subscriber-hosted cross-BC aggregate write in the agent BC.

## v1 gate (deterministic, no LLM)

  - context == CautionProposal AND author is a registered CautionDrafter
    (else skipped, no Decision: not ours / its own output / other contexts).
  - choice == ProposeNotice (Caution / Warning / Supersede stay human-gated).
  - confidence >= the high band (a SOFT gate: CautionDrafter confidence is
    self-reported / uncalibrated, so Notice-only + reversibility are the real
    safety).
  - no active Caution already on the target (find_active_for_run with
    min_severity="Notice", per-target).
  - the proposed tuple passes Caution VO validation (else deferred, never
    raised, so a bad LLM tuple cannot wedge the shared bookmark).
  - no matching Notice this promoter previously registered was Retired by an
    operator (find_retired_for_target on target_kind+target_id+category+
    authored_by=CautionPromoter); a retirement is a deliberate operator
    override, so the agent respects it and does not re-create -> deferred.
  - Authorize permits PromoteCautionProposal (parity with the human path).

## Idempotency

Both the CautionPromotion Decision id and the registered Caution id are
deterministic uuid5 from the proposal decision_id, so re-delivery is a
ConcurrencyError no-op.

## Off by default

Registered only when `settings.caution_promoter_enabled` (default False). The
operator-retirement-memory guard (Lock 5) -- the prerequisite to enabling this
operationally -- is now implemented (the `find_retired_for_target` gate arm
above), so a deployment MAY opt in. It stays default-off because it is CORA's
first no-human-in-the-loop artifact: enabling carries the Lock 15 obligation of
a periodic operator precision-review of agent-authored Notices (via
`list_cautions(authored_by=CAUTION_PROMOTER_AGENT_ID)`). A future agent-retire
path would require threading the human retirer through the retire/supersede
projection arms and keying the guard on it; today no agent retires a Caution,
so the promoter's own authored_by is the correct key. See
[[project-caution-promoter-design]].
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.aggregates.agent import load_agent
from cora.agent.errors import (
    CautionProposalMalformedError,
    CautionProposalNotActionableError,
    DecisionNotCautionProposalError,
)
from cora.agent.features.promote_caution_proposal.command import PromoteCautionProposal
from cora.agent.features.promote_caution_proposal.decider import ProposedCautionView, decide
from cora.agent.seed_caution_drafter import CAUTION_DRAFTER_AGENT_KIND
from cora.agent.seed_caution_promoter import CAUTION_PROMOTER_AGENT_ID
from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionRegistered,
    CautionSeverity,
    CautionTag,
    CautionTarget,
    CautionText,
    CautionWorkaround,
    ProcedureTarget,
    ensure_expires_at_future,
)
from cora.caution.aggregates.caution import event_type_name as caution_event_type_name
from cora.caution.aggregates.caution import to_payload as caution_to_payload
from cora.decision.aggregates.decision import (
    CONFIDENCE_BAND_HIGH_MIN,
    DECISION_CONTEXT_CAUTION_PROMOTION,
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    DecisionRegistered,
    DecisionRule,
    event_type_name,
    load_decision,
    to_payload,
    validate_confidence,
    validate_inputs,
    validate_reasoning,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from cora.decision.aggregates.decision import Decision
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports import Authorize, CautionLookup, Clock, IdGenerator
    from cora.infrastructure.ports.event_store import EventStore, StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike

_DECISION_STREAM_TYPE = "Decision"
_CAUTION_STREAM_TYPE = "Caution"
_COMMAND_NAME = "CautionPromoterSubscriber"
_PROMOTE_COMMAND_NAME = "PromoteCautionProposal"
_DECISION_RULE = "agent:CautionPromoter:v1"
_PROPOSAL_CONTEXT = "CautionProposal"
_AUTO_PROMOTE_CHOICE = "ProposeNotice"

# Stable namespace for deriving deterministic ids from the proposal
# decision_id. Distinct from the other agents' namespaces (dddd block).
_CAUTION_PROMOTER_NAMESPACE = UUID("01900000-0000-7000-8000-0000dddd0002")

_log = get_logger(__name__)


def _derive_decision_id(proposal_decision_id: UUID) -> UUID:
    """Deterministic CautionPromotion Decision id from the proposal id."""
    return uuid5(_CAUTION_PROMOTER_NAMESPACE, f"decision:{proposal_decision_id}")


def _derive_caution_id(proposal_decision_id: UUID) -> UUID:
    """Deterministic registered-Caution id from the proposal id."""
    return uuid5(_CAUTION_PROMOTER_NAMESPACE, f"caution:{proposal_decision_id}")


def _build_target(view: ProposedCautionView) -> CautionTarget:
    if view.target_kind == "Asset":
        return AssetTarget(asset_id=view.target_id)
    if view.target_kind == "Procedure":
        return ProcedureTarget(procedure_id=view.target_id)
    msg = f"Unknown target_kind {view.target_kind!r}; expected 'Asset' or 'Procedure'"
    raise ValueError(msg)


class CautionPromoterSubscriber:
    """Reaction: CautionProposal -> one CautionPromotion Decision (+ Caution on Promote).

    Constructed by `make_caution_promoter_subscriber` from the Kernel; satisfies
    the `Reaction` Protocol structurally. Deterministic (no LLM round-trip), so
    `batch_size = 1` keeps the cross-BC append + ConcurrencyError pattern simple
    rather than for pool-starvation reasons.
    """

    name = "caution_promoter"
    subscribed_event_types = frozenset({"DecisionRegistered"})
    batch_size = 1

    def __init__(
        self,
        *,
        event_store: EventStore,
        authz: Authorize,
        caution_lookup: CautionLookup,
        clock: Clock,
        id_generator: IdGenerator,
        confidence_threshold: float = CONFIDENCE_BAND_HIGH_MIN,
    ) -> None:
        self.event_store = event_store
        self.authz = authz
        self.caution_lookup = caution_lookup
        self.clock = clock
        self.id_generator = id_generator
        self.confidence_threshold = confidence_threshold

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        """Process one DecisionRegistered; no-op for anything but a promotable proposal."""
        _ = conn  # not used at v1 (mirrors the other agent subscribers)
        # Cheap context filter FIRST: the worker dispatches on event_type only,
        # so every DecisionRegistered in the facility (incl. our own
        # CautionPromotion output) lands here. Skip non-proposals before any load.
        if event.event_type != "DecisionRegistered":
            return
        if event.payload.get("context") != _PROPOSAL_CONTEXT:
            return
        try:
            await self._handle_proposal(event)
        except Exception:
            # A malformed event must never wedge the shared subscriber bookmark
            # (the deferred operator escape-hatch does not exist yet). Log and
            # advance; the gate already defers known-bad tuples.
            _log.exception("caution_promoter.apply_failed", proposal_event_id=str(event.event_id))

    async def _handle_proposal(self, event: StoredEvent) -> None:
        proposal_id = UUID(event.payload["decision_id"])

        actor = await load_actor(self.event_store, CAUTION_PROMOTER_AGENT_ID)
        if actor is None or not actor.active:
            return  # not seeded yet, or operator-deactivated: stand down

        decision = await load_decision(self.event_store, proposal_id)
        if decision is None:
            return

        # Provenance gate: only act on proposals authored by a registered
        # CautionDrafter agent (mirror promote_caution_proposal). This also
        # excludes the promoter's own CautionPromotion output and any other
        # author's Decision.
        producer = await load_agent(self.event_store, decision.decided_by)
        if producer is None or producer.kind.value != CAUTION_DRAFTER_AGENT_KIND:
            return

        try:
            view = decide(decision, PromoteCautionProposal(decision_id=proposal_id))
        except (
            DecisionNotCautionProposalError,
            CautionProposalNotActionableError,
            CautionProposalMalformedError,
        ):
            return  # NoAction / malformed: nothing to promote

        choice, reason = await self._evaluate(view, decision)

        decision_id = _derive_decision_id(proposal_id)
        if not await self._record_promotion_decision(
            decision_id=decision_id,
            proposal_id=proposal_id,
            choice=choice,
            reason=reason,
            view=view,
        ):
            return  # ConcurrencyError: this proposal was already processed

        if choice == "Promote":
            await self._write_caution(view=view, proposal_id=proposal_id)

    async def _evaluate(self, view: ProposedCautionView, decision: Decision) -> tuple[str, str]:
        """Pure-ish gate (one conflict read + one Authorize read); returns (choice, reason)."""
        if view.choice != _AUTO_PROMOTE_CHOICE:
            return "PromotionDeferred", f"choice {view.choice} above Notice; operator-gated"
        if decision.confidence is None or decision.confidence < self.confidence_threshold:
            return "PromotionDeferred", "proposal confidence below the auto-promote threshold"

        asset_ids: frozenset[UUID] = (
            frozenset({view.target_id}) if view.target_kind == "Asset" else frozenset()
        )
        procedure_ids: frozenset[UUID] = (
            frozenset({view.target_id}) if view.target_kind == "Procedure" else frozenset()
        )
        existing = await self.caution_lookup.find_active_for_run(
            asset_ids=asset_ids,
            procedure_ids=procedure_ids,
            min_severity="Notice",
        )
        if existing:
            return "PromotionConflicted", "an active Caution already covers the target"

        # Re-validate the LLM-authored tuple through the Caution public VOs before
        # committing to Promote, so an invalid tuple defers rather than raising
        # mid-write.
        try:
            _validate_caution_fields(view)
        except ValueError:
            return "PromotionDeferred", "proposed caution failed Caution validation"

        # GOV-1 (Lock 5) operator-retirement-memory guard: if a matching Notice
        # this promoter previously registered was deliberately Retired by an
        # operator, do not re-create it. Keyed on the promoter's own authored_by
        # (the only agent-authored Cautions are its registrations); only Retired
        # rows veto, so a Superseded predecessor does not.
        #
        # Trade-off (gate-review R4): this keys on the promoter's OWN authored_by
        # ("do not resurrect my own retired output"), which UNDER-suppresses a
        # human-authored retired Notice on the same target+category. The
        # conservative alternative is author-agnostic (respect ANY operator
        # retirement), which OVER-suppresses a genuinely-new agent heads-up.
        # v1 takes the precise narrowing; widen to author-agnostic if operators
        # report the agent re-raising heads-up they dismissed.
        retired = await self.caution_lookup.find_retired_for_target(
            target_kind=view.target_kind,
            target_id=view.target_id,
            category=view.category,
            authored_by=CAUTION_PROMOTER_AGENT_ID,
        )
        if retired:
            return (
                "PromotionDeferred",
                "a matching Notice was previously retired by an operator; respecting the override",
            )

        authz = await self.authz.authorize(
            principal_id=CAUTION_PROMOTER_AGENT_ID,
            command_name=_PROMOTE_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=NIL_SENTINEL_ID,
        )
        if isinstance(authz, Deny):
            return "PromotionDeferred", "not authorized to promote (Authorize denied)"

        return "Promote", "auto-promoted high-confidence Notice-only proposal"

    async def _record_promotion_decision(
        self,
        *,
        decision_id: UUID,
        proposal_id: UUID,
        choice: str,
        reason: str,
        view: ProposedCautionView,
    ) -> bool:
        """Append the CautionPromotion Decision. False on ConcurrencyError (idempotent)."""
        now = self.clock.now()
        domain_event = DecisionRegistered(
            decision_id=decision_id,
            decided_by=ActorId(CAUTION_PROMOTER_AGENT_ID),
            context=DecisionContext(DECISION_CONTEXT_CAUTION_PROMOTION).value,
            choice=DecisionChoice(choice).value,
            parent_id=proposal_id,
            override_kind=None,
            rule=DecisionRule(_DECISION_RULE).value,
            reasoning=validate_reasoning(reason),
            confidence=validate_confidence(None),
            confidence_source=DecisionConfidenceSource.SELF_REPORTED,
            alternatives=(),
            inputs=validate_inputs(
                {
                    "proposal_decision_id": str(proposal_id),
                    "proposal_choice": view.choice,
                    "severity": view.severity,
                    "target_kind": view.target_kind,
                    "target_id": str(view.target_id),
                }
            ),
            reasoning_signature=None,
            occurred_at=now,
        )
        new_event = to_new_event(
            event_type=event_type_name(domain_event),
            payload=to_payload(domain_event),
            occurred_at=now,
            event_id=uuid5(decision_id, "event:0"),
            command_name=_COMMAND_NAME,
            correlation_id=self.id_generator.new_id(),
            causation_id=None,
            principal_id=CAUTION_PROMOTER_AGENT_ID,
        )
        try:
            await self.event_store.append(
                stream_type=_DECISION_STREAM_TYPE,
                stream_id=decision_id,
                expected_version=0,
                events=[new_event],
            )
        except ConcurrencyError:
            _log.info("caution_promoter.already_processed", choice=choice)
            return False
        _log.info("caution_promoter.decision", choice=choice)
        return True

    async def _write_caution(self, *, view: ProposedCautionView, proposal_id: UUID) -> None:
        """Pattern C: register a live Caution with a deterministic id (idempotent)."""
        now = self.clock.now()
        caution_id = _derive_caution_id(proposal_id)
        # The promoter never sets an expiry (Notice-only, indefinite until an
        # operator retires it), so this guards a future change to that policy
        # rather than the current None; it is the same write-site invariant the
        # human promote_caution_proposal path calls.
        ensure_expires_at_future(None, now)
        register_event = CautionRegistered(
            caution_id=caution_id,
            target=_build_target(view),
            category=CautionCategory(view.category).value,
            severity=CautionSeverity(view.severity).value,
            text=CautionText(view.title).value,
            workaround=CautionWorkaround(view.body).value,
            tags=frozenset(CautionTag(t).value for t in view.tags),
            authored_by=ActorId(CAUTION_PROMOTER_AGENT_ID),
            expires_at=None,
            propagate_to_children=False,
            parent_id=None,
            occurred_at=now,
        )
        envelope = to_new_event(
            event_type=caution_event_type_name(register_event),
            payload=caution_to_payload(register_event),
            occurred_at=now,
            event_id=uuid5(caution_id, "event:0"),
            command_name=_PROMOTE_COMMAND_NAME,
            correlation_id=self.id_generator.new_id(),
            causation_id=None,
            principal_id=CAUTION_PROMOTER_AGENT_ID,
        )
        try:
            await self.event_store.append(
                stream_type=_CAUTION_STREAM_TYPE,
                stream_id=caution_id,
                expected_version=0,
                events=[envelope],
            )
        except ConcurrencyError:
            _log.info("caution_promoter.caution_already_written", caution_id=str(caution_id))
            return
        _log.info("caution_promoter.promoted", caution_id=str(caution_id), severity=view.severity)


def _validate_caution_fields(view: ProposedCautionView) -> None:
    """Run the Caution public VOs to validate the proposed tuple; raises ValueError."""
    CautionCategory(view.category)
    CautionSeverity(view.severity)
    CautionText(view.title)
    CautionWorkaround(view.body)
    for tag in view.tags:
        CautionTag(tag)
    _build_target(view)


def make_caution_promoter_subscriber(deps: Kernel) -> CautionPromoterSubscriber:
    """Build the CautionPromoter subscriber closed over the shared deps."""
    return CautionPromoterSubscriber(
        event_store=deps.event_store,
        authz=deps.authz,
        caution_lookup=deps.caution_lookup,
        clock=deps.clock,
        id_generator=deps.id_generator,
    )


__all__ = ["CautionPromoterSubscriber", "make_caution_promoter_subscriber"]
