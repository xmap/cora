"""Reaction (consequence gate, Gate IV): RatificationRequested -> hold the run.

When a consequence-classed command (StopRun) is refused for lack of a co-signature,
the operator requests a ratification; this subscriber, acting as the pinned
RatificationEnforcer agent, parks the target run in the SAME shared hold the
kill-switch uses (RunHeld), pending the co-sign.

Pattern C write (not the hold_run slice): cora.agent may depend on
cora.run.aggregates but NOT cora.run.features (tach boundary). So it loads the run,
guards status == Running in-process, authorizes HoldRun as its own principal, and
appends RunHeld with optimistic concurrency, mirroring authority_revocation_holder.
Kind-blind (the target run is a UUID from the event payload; actor kind is never
read). Idempotent + fail-safe: an already-Held / terminal / missing run is a
logged no-op, and a lost concurrency race or Authorize Deny is swallowed, so a
redelivered event cannot wedge the shared bookmark.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent.seed_ratification_enforcer import RATIFICATION_ENFORCER_AGENT_ID
from cora.agent.subscribers._ratification_shared import (
    HOLD_COMMAND_NAME,
    RUN_STREAM_TYPE,
    enforcer_standing_down,
    ratification_claim_id,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import HOLD_CAUSE_RATIFICATION, RunHeld, RunStatus
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import fold as fold_run
from cora.run.aggregates.run import from_stored as run_from_stored
from cora.run.aggregates.run import to_payload as run_to_payload

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports import Authorize, Clock, EventStore, IdGenerator
    from cora.infrastructure.ports.event_store import StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike

_log = get_logger(__name__)

# Terminal runs cannot be held; an already-HELD run can, under a distinct claim.
_HOLDABLE_STATUSES = (RunStatus.RUNNING, RunStatus.HELD)


class RatificationHoldSubscriber:
    """Reaction: RatificationRequested -> hold the target run (park pending co-sign)."""

    name = "ratification_hold"
    subscribed_event_types = frozenset({"RatificationRequested"})
    batch_size = 1

    def __init__(
        self,
        *,
        event_store: EventStore,
        authz: Authorize,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self.event_store = event_store
        self.authz = authz
        self.clock = clock
        self.id_generator = id_generator

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        _ = conn  # cross-BC writes go through the event store, like the other subscribers
        if event.event_type != "RatificationRequested":
            return
        try:
            if await enforcer_standing_down(self.event_store):
                return
            run_id = UUID(event.payload["target_action_id"])
            await self._hold(run_id)
        except Exception:
            _log.exception(
                "ratification_hold.apply_failed",
                ratification_event_id=str(event.event_id),
            )

    async def _hold(self, run_id: UUID) -> None:
        stored, version = await self.event_store.load(RUN_STREAM_TYPE, run_id)
        if not stored:
            _log.info("ratification_hold.run_not_found", run_id=str(run_id))
            return
        state = fold_run([run_from_stored(s) for s in stored])
        if state is None or state.status not in _HOLDABLE_STATUSES:
            # Terminal only. An ALREADY-HELD run is holdable: another concern
            # may be holding it, and this gate must still record its own claim
            # or its cause goes unenforced when that concern releases. Guarding
            # on RUNNING alone is what made the reproduced ordering fault
            # possible.
            _log.info("ratification_hold.not_holdable", run_id=str(run_id))
            return
        claim_id = ratification_claim_id(run_id)
        if any(active_id == claim_id for active_id, _ in state.hold_claims):
            # This gate already holds it (re-delivery, or a second concurrent
            # ratification on the same run). Idempotent no-op.
            _log.info("ratification_hold.already_claimed", run_id=str(run_id))
            return
        authz = await self.authz.authorize(
            principal_id=RATIFICATION_ENFORCER_AGENT_ID,
            command_name=HOLD_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=NIL_SENTINEL_ID,
        )
        if isinstance(authz, Deny):
            _log.info("ratification_hold.unauthorized", run_id=str(run_id))
            return
        now = self.clock.now()
        held = RunHeld(
            run_id=run_id,
            decided_by_decision_id=None,
            claim_id=claim_id,
            cause=HOLD_CAUSE_RATIFICATION,
            occurred_at=now,
        )
        envelope = to_new_event(
            event_type=run_event_type_name(held),
            payload=run_to_payload(held),
            occurred_at=now,
            event_id=self.id_generator.new_id(),
            command_name=HOLD_COMMAND_NAME,
            correlation_id=self.id_generator.new_id(),
            causation_id=None,
            principal_id=RATIFICATION_ENFORCER_AGENT_ID,
        )
        try:
            await self.event_store.append(
                stream_type=RUN_STREAM_TYPE,
                stream_id=run_id,
                expected_version=version,
                events=[envelope],
            )
        except ConcurrencyError:
            _log.info("ratification_hold.lost_race", run_id=str(run_id))
            return
        _log.info("ratification_hold.held", run_id=str(run_id))


def make_ratification_hold_subscriber(deps: Kernel) -> RatificationHoldSubscriber:
    """Build the RatificationHold subscriber closed over the shared deps."""
    return RatificationHoldSubscriber(
        event_store=deps.event_store,
        authz=deps.authz,
        clock=deps.clock,
        id_generator=deps.id_generator,
    )


__all__ = ["RatificationHoldSubscriber", "make_ratification_hold_subscriber"]
