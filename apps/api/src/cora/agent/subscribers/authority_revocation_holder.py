"""Reaction (kill-switch K3): a PolicyGrantRevoked -> hold the revoked
principal's in-flight Runs.

AuthorityRevocationHolder is CORA's deterministic kill-switch subscriber. It
reacts to `PolicyGrantRevoked` (the K1 trigger event), asks the
`RunActorInvolvementLookup` (K2) for the in-flight Runs the revoked principal
drives, and holds each -- pausing the runs a principal can no longer be trusted
to drive. It records one
`Decision(context=AuthorityRevocationHold, parent_id=<revocation event>)` per
run for provenance.

## Cross-BC write via Pattern C (not the hold_run handler)

The `cora.agent` package may depend on `cora.run.aggregates` but NOT on
`cora.run.features` (the tach BC boundary; the RunSupervisor loop is exempt only
because it lives in `cora.api`). So, like CautionPromoter writing a Caution, this
subscriber does the hold itself: load the Run, guard `Running` in-process,
authorize as its own principal, construct `RunHeld` from `cora.run.aggregates`,
and append with optimistic concurrency. This duplicates the small hold_run
decider guard rather than crossing the boundary.

## Order of operations: hold FIRST, record SECOND

The hold is the safety-critical, durable act; the Decision is best-effort
provenance. So each run is held before its Decision is written. If the Decision
append fails, the run is still safely held (the RunHeld event + its envelope
principal are themselves an audit trail); a re-delivery re-derives the same
Decision id and no-ops on ConcurrencyError.

## Holdable-status guard, and why it is no longer Running-only

The holder acted on Running runs only, deferring on anything else. That dropped
the revocation on the floor whenever the run was already held by another concern:
`HoldDeferred` writes a Decision but NO Run event, so when that concern released
its hold the run resumed with the revoked principal's runs unpaused, and the
kill-switch never fired again (one `PolicyGrantRevoked`, idempotent re-delivery,
no sweep). See [[project-hold-claim-ordering-fault]].

It now holds a Running OR already-Held run, recording its own cause-scoped claim.
A terminal or missing run still records `HoldDeferred` (no event), never raised,
so a stale K2 projection row cannot wedge the shared bookmark. Re-delivery is
idempotent via the derived claim id. The load-then-append is guarded by optimistic
concurrency: if the Run advanced between the read and the write, the append's
ConcurrencyError is caught and folded to HoldDeferred (the next delivery, if any,
re-evaluates fresh).

## Kind-blind

Attribution and the hold never read actor kind: a revoked human's runs and a
revoked agent's runs are held by the same code. The revoked principal is just a
UUID from the event payload.

## Authorization

The holder authorizes HoldRun through the Authorize port as its own pinned agent
principal. Under TrustAuthorize the operator's Policy must grant it {HoldRun};
without the grant the Deny is recorded as HoldDeferred, so the kill-switch
degrades safe rather than crashing the worker.

## On by default

Unlike the LLM subscribers (gated on ANTHROPIC_API_KEY) and CautionPromoter
(gated on an off-by-default setting), the holder registers unconditionally: a
kill-switch that must be turned on is not a kill-switch. Holding is reversible
(resume_run exists), so the default-on posture matches the safety intent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_authority_revocation_holder import (
    AUTHORITY_REVOCATION_HOLDER_AGENT_ID,
)
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_AUTHORITY_REVOCATION_HOLD,
    DecisionConfidenceSource,
    DecisionRegistered,
    event_type_name,
    to_payload,
    validate_confidence,
    validate_inputs,
    validate_reasoning,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import (
    HOLD_CAUSE_AUTHORITY_REVOCATION,
    RunHeld,
    RunStatus,
    derive_claim_id,
)
from cora.run.aggregates.run import (
    event_type_name as run_event_type_name,
)
from cora.run.aggregates.run import (
    fold as fold_run,
)
from cora.run.aggregates.run import (
    from_stored as run_from_stored,
)
from cora.run.aggregates.run import (
    to_payload as run_to_payload,
)
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports import Authorize, Clock, IdGenerator, RunActorInvolvementLookup
    from cora.infrastructure.ports.event_store import EventStore, StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike

_DECISION_STREAM_TYPE = "Decision"
_RUN_STREAM_TYPE = "Run"
_HOLD_COMMAND_NAME = "HoldRun"
_COMMAND_NAME = "AuthorityRevocationHolderSubscriber"
_DECISION_RULE = "agent:AuthorityRevocationHolder:v1"
_TRIGGER_EVENT_TYPE = "PolicyGrantRevoked"

# Stable namespace for deriving deterministic Decision ids from the (revocation
# event, run) pair. Follows the sibling suffix convention (...0000<block>0002,
# cf. aaaa0002 / bbbb0002 / dddd0002) in the holder's own b111 block; distinct
# from every other agent's namespace.
_HOLDER_NAMESPACE = UUID("01900000-0000-7000-8000-0000b1110002")

# Terminal runs cannot be held. An already-HELD run CAN: another concern may be
# holding it, and a safety hold that declines to record itself is a safety hold
# that silently expires when that concern releases.
_HOLDABLE_STATUSES = (RunStatus.RUNNING, RunStatus.HELD)

_log = get_logger(__name__)


def _derive_decision_id(revocation_event_id: UUID, run_id: UUID) -> UUID:
    """Deterministic AuthorityRevocationHold Decision id, one per (revocation, run).

    Keyed on the triggering event id (not the policy or principal) so a
    re-delivery of the same PolicyGrantRevoked derives the same ids and no-ops,
    while a later, distinct revocation of the same principal gets fresh ids.
    """
    return uuid5(_HOLDER_NAMESPACE, f"decision:{revocation_event_id}:{run_id}")


class AuthorityRevocationHolderSubscriber:
    """Reaction: PolicyGrantRevoked -> hold each in-flight Run of the revoked principal.

    Constructed by `make_authority_revocation_holder_subscriber` from the Kernel;
    satisfies the `Reaction` Protocol structurally. Deterministic (no LLM), so
    `batch_size = 1` keeps the per-run hold + Decision append sequence simple.
    """

    name = "authority_revocation_holder"
    subscribed_event_types = frozenset({"PolicyGrantRevoked"})
    batch_size = 1

    def __init__(
        self,
        *,
        event_store: EventStore,
        run_actor_involvement_lookup: RunActorInvolvementLookup,
        authz: Authorize,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self.event_store = event_store
        self.run_actor_involvement_lookup = run_actor_involvement_lookup
        self.authz = authz
        self.clock = clock
        self.id_generator = id_generator

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        """Process one PolicyGrantRevoked; hold the revoked principal's in-flight runs."""
        # conn unused: cross-BC writes go through the event store, like the other subscribers.
        _ = conn
        if event.event_type != _TRIGGER_EVENT_TYPE:
            return
        try:
            await self._handle_revocation(event)
        except Exception:
            # A malformed event or transient fault must never wedge the shared
            # subscriber bookmark (no operator escape-hatch yet). Log and advance;
            # a re-delivery replays idempotently (deterministic Decision ids +
            # the Running-only guard + ConcurrencyError swallow).
            _log.exception(
                "authority_revocation_holder.apply_failed",
                revocation_event_id=str(event.event_id),
            )

    async def _handle_revocation(self, event: StoredEvent) -> None:
        actor = await load_actor(self.event_store, AUTHORITY_REVOCATION_HOLDER_AGENT_ID)
        if actor is None or not actor.active:
            # Not seeded yet (bootstrap runs before the worker), or the operator
            # deactivated the holder Actor. Stand down. Same operator-deactivation
            # revocation surface as every sibling agent (load_actor().active),
            # deliberately kept uniform: an operator disables the kill-switch the
            # same way they disable any agent, not through a bespoke gate.
            return

        revoked_principal_id = UUID(event.payload["principal_id"])
        run_ids = await self.run_actor_involvement_lookup.runs_driven_by(revoked_principal_id)
        if not run_ids:
            _log.info(
                "authority_revocation_holder.no_in_flight_runs",
                revoked_principal_id=str(revoked_principal_id),
            )
            return

        for run_id in run_ids:
            # Isolate each run: a fault holding (or recording) one run must NOT
            # abandon the siblings. For a kill-switch, silent partial enforcement
            # (runs #2..N left Running because run #1 raised) is the worst mode, so
            # the blast radius is bounded to the single run. The bookmark still
            # advances after this event, so a run dropped here is NOT redelivered:
            # the error log is the operator's signal to intervene (resume/re-hold
            # by hand). This is the wedged-bookmark escape-hatch trigger from the
            # subscriber-framework widening plan; the holder is the 4th Reaction.
            try:
                await self._hold_one(event=event, run_id=run_id)
            except Exception:
                _log.exception(
                    "authority_revocation_holder.hold_one_failed",
                    revocation_event_id=str(event.event_id),
                    run_id=str(run_id),
                )

    async def _hold_one(self, *, event: StoredEvent, run_id: UUID) -> None:
        """Hold one run (safety act), then record its Decision (provenance)."""
        decision_id = _derive_decision_id(event.event_id, run_id)
        choice, reason = await self._issue_hold(run_id=run_id, decision_id=decision_id)
        await self._record_hold_decision(
            decision_id=decision_id,
            revocation_event_id=event.event_id,
            run_id=run_id,
            choice=choice,
            reason=reason,
        )

    async def _issue_hold(self, *, run_id: UUID, decision_id: UUID) -> tuple[str, str]:
        """Pattern C hold: load + guard Running + authorize + append RunHeld.

        Returns (choice, reason). Every non-hold path folds to HoldDeferred and is
        never raised, so a stale row / lost race / denied authz cannot wedge the
        bookmark.
        """
        stored, version = await self.event_store.load(_RUN_STREAM_TYPE, run_id)
        if not stored:
            return "HoldDeferred", "run not found (stale involvement projection row)"
        state = fold_run([run_from_stored(s) for s in stored])
        if state is None or state.status not in _HOLDABLE_STATUSES:
            return "HoldDeferred", "run is terminal"
        # An already-HELD run is HOLDABLE. This is the fix: the kill-switch used
        # to defer on any non-Running status, so a run held by the consequence
        # gate awaiting a co-signature absorbed the revocation without recording
        # it, and the gate's later release resumed the run with the revocation
        # unenforced. The safety hold now records its own claim and outlives that
        # release. See [[project-hold-claim-ordering-fault]].
        claim_id = derive_claim_id(run_id, HOLD_CAUSE_AUTHORITY_REVOCATION)
        if any(active_id == claim_id for active_id, _ in state.hold_claims):
            return "HoldDeferred", "already held by this kill-switch (re-delivery)"

        authz = await self.authz.authorize(
            principal_id=AUTHORITY_REVOCATION_HOLDER_AGENT_ID,
            command_name=_HOLD_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=NIL_SENTINEL_ID,
        )
        if isinstance(authz, Deny):
            return "HoldDeferred", "not authorized to hold (Authorize denied)"

        now = self.clock.now()
        held = RunHeld(
            run_id=run_id,
            decided_by_decision_id=decision_id,
            claim_id=claim_id,
            cause=HOLD_CAUSE_AUTHORITY_REVOCATION,
            occurred_at=now,
        )
        envelope = to_new_event(
            event_type=run_event_type_name(held),
            payload=run_to_payload(held),
            occurred_at=now,
            event_id=self.id_generator.new_id(),
            command_name=_HOLD_COMMAND_NAME,
            correlation_id=self.id_generator.new_id(),
            causation_id=None,
            principal_id=AUTHORITY_REVOCATION_HOLDER_AGENT_ID,
        )
        try:
            await self.event_store.append(
                stream_type=_RUN_STREAM_TYPE,
                stream_id=run_id,
                expected_version=version,
                events=[envelope],
            )
        except ConcurrencyError:
            return "HoldDeferred", "run advanced concurrently (lost the hold race)"
        _log.info("authority_revocation_holder.held", run_id=str(run_id))
        return "Held", "held the revoked principal's in-flight run"

    async def _record_hold_decision(
        self,
        *,
        decision_id: UUID,
        revocation_event_id: UUID,
        run_id: UUID,
        choice: str,
        reason: str,
    ) -> None:
        """Append the AuthorityRevocationHold Decision. No-op on ConcurrencyError (idempotent)."""
        now = self.clock.now()
        domain_event = DecisionRegistered(
            decision_id=decision_id,
            decided_by=ActorId(AUTHORITY_REVOCATION_HOLDER_AGENT_ID),
            context=DECISION_CONTEXT_AUTHORITY_REVOCATION_HOLD,
            choice=choice,
            parent_id=revocation_event_id,
            override_kind=None,
            rule=_DECISION_RULE,
            reasoning=validate_reasoning(reason),
            confidence=validate_confidence(None),
            confidence_source=DecisionConfidenceSource.SELF_REPORTED,
            alternatives=(),
            inputs=validate_inputs(
                {
                    "revocation_event_id": str(revocation_event_id),
                    "run_id": str(run_id),
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
            principal_id=AUTHORITY_REVOCATION_HOLDER_AGENT_ID,
        )
        try:
            await self.event_store.append(
                stream_type=_DECISION_STREAM_TYPE,
                stream_id=decision_id,
                expected_version=0,
                events=[new_event],
            )
        except ConcurrencyError:
            _log.info("authority_revocation_holder.decision_already_recorded", choice=choice)
            return
        _log.info("authority_revocation_holder.decision", choice=choice, run_id=str(run_id))


def make_authority_revocation_holder_subscriber(
    deps: Kernel,
) -> AuthorityRevocationHolderSubscriber:
    """Build the AuthorityRevocationHolder subscriber closed over the shared deps."""
    return AuthorityRevocationHolderSubscriber(
        event_store=deps.event_store,
        run_actor_involvement_lookup=deps.run_actor_involvement_lookup,
        authz=deps.authz,
        clock=deps.clock,
        id_generator=deps.id_generator,
    )


__all__ = [
    "AuthorityRevocationHolderSubscriber",
    "make_authority_revocation_holder_subscriber",
]
