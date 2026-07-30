"""Reaction (consequence gate, Gate IV): a settled Ratification -> resume the run.

Reacts to BOTH RatificationGranted and RatificationDenied and un-parks the run
this enforcer held: Granted means the co-sign arrived (the operator can re-issue
the now-covered stop, which the gate admits); Denied means the co-sign was refused
(the run returns to Running and the stop stays un-admitted, since coverage is never
Granted). Leaving a denied run Held forever would make the "reversible hold"
un-reversible, so denial auto-resumes symmetrically.

CORRELATION (the load-bearing guard): the release discharges ONLY this gate's own
hold claim, and resumes the run only when no other claim is active. Because
several concerns can hold one run (the kill-switch on a revoked grant, an
operator, the supervisor on an envelope breach), a settled ratification has three
outcomes, not one: resume (this gate was the last holder), release-and-stay-held
(others remain), or stand down (this gate never held it).

This replaced a backward scan for the most recent `RunHeld` comparing envelope
principals. That guard was correct for the case it covered and blind to the one
that mattered: every holder used to no-op on an already-held run, so a hold
arriving during this gate's co-signature wait left NO event to be found, and the
grant resumed the run with that concern's cause unenforced.

Pattern C write (not the resume_run slice): loads the run, guards, authorizes
ResumeRun as its own principal, appends RunResumed with optimistic concurrency.
Granted/Denied carry only ratification_id, so it loads the Ratification aggregate
(the sole reason cora.agent depends on cora.trust.aggregates) to resolve the
target run. Kind-blind; idempotent + fail-safe (already-Running / foreign-hold /
lost-race / Deny are logged no-ops).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent.seed_ratification_enforcer import RATIFICATION_ENFORCER_AGENT_ID
from cora.agent.subscribers._ratification_shared import (
    RESUME_COMMAND_NAME,
    RUN_STREAM_TYPE,
    enforcer_holds_claim,
    enforcer_standing_down,
    others_still_holding,
    ratification_claim_id,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import (
    HOLD_CAUSE_RATIFICATION,
    HoldClaimReleased,
    RunResumed,
    RunStatus,
    fold_hold_claims_from_stored,
)
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import fold as fold_run
from cora.run.aggregates.run import from_stored as run_from_stored
from cora.run.aggregates.run import to_payload as run_to_payload
from cora.trust.aggregates.ratification import load_ratification

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports import Authorize, Clock, EventStore, IdGenerator
    from cora.infrastructure.ports.event_store import StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike

_log = get_logger(__name__)

_SETTLED_EVENT_TYPES = ("RatificationGranted", "RatificationDenied")


class RatificationReleaseSubscriber:
    """Reaction: a settled Ratification (Granted OR Denied) -> resume the parked run."""

    name = "ratification_release"
    subscribed_event_types = frozenset({"RatificationGranted", "RatificationDenied"})
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
        _ = conn
        if event.event_type not in _SETTLED_EVENT_TYPES:
            return
        try:
            if await enforcer_standing_down(self.event_store):
                return
            # Granted/Denied carry only ratification_id; resolve the target run by
            # loading the Ratification aggregate (carries target_action_id).
            ratification = await load_ratification(
                self.event_store, UUID(event.payload["ratification_id"])
            )
            if ratification is None:
                return
            await self._resume(ratification.target_action_id)
        except Exception:
            _log.exception(
                "ratification_release.apply_failed",
                ratification_event_id=str(event.event_id),
            )

    async def _resume(self, run_id: UUID) -> None:
        stored, version = await self.event_store.load(RUN_STREAM_TYPE, run_id)
        if not stored:
            _log.info("ratification_release.run_not_found", run_id=str(run_id))
            return
        state = fold_run([run_from_stored(s) for s in stored])
        if state is None or state.status is not RunStatus.HELD:
            _log.info("ratification_release.not_held", run_id=str(run_id))
            return
        claims = fold_hold_claims_from_stored(stored)
        if not enforcer_holds_claim(claims, run_id):
            # Held, but not by this gate (kill-switch / operator / supervisor).
            # Clearing someone else's hold would invert their intent, so stand
            # down: the other holder owns it.
            _log.info("ratification_release.foreign_hold", run_id=str(run_id))
            return
        blocking = others_still_holding(claims, run_id)
        authz = await self.authz.authorize(
            principal_id=RATIFICATION_ENFORCER_AGENT_ID,
            command_name=RESUME_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=NIL_SENTINEL_ID,
        )
        if isinstance(authz, Deny):
            _log.info("ratification_release.unauthorized", run_id=str(run_id))
            return
        now = self.clock.now()
        claim_id = ratification_claim_id(run_id)
        # THE release rule. Discharge this gate's claim either way, but resume
        # the run only when nothing else is holding it. Emitting RunResumed
        # while `blocking` is non-empty is exactly the premature release this
        # gate used to perform when a hold had been dropped rather than
        # recorded.
        discharge: RunResumed | HoldClaimReleased
        if blocking:
            discharge = HoldClaimReleased(
                run_id=run_id,
                claim_id=claim_id,
                cause=HOLD_CAUSE_RATIFICATION,
                decided_by_decision_id=None,
                occurred_at=now,
            )
        else:
            discharge = RunResumed(
                run_id=run_id,
                occurred_at=now,
                decided_by_decision_id=None,
                released_claim_id=claim_id,
            )
        envelope = to_new_event(
            event_type=run_event_type_name(discharge),
            payload=run_to_payload(discharge),
            occurred_at=now,
            event_id=self.id_generator.new_id(),
            command_name=RESUME_COMMAND_NAME,
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
            _log.info("ratification_release.lost_race", run_id=str(run_id))
            return
        if blocking:
            _log.info(
                "ratification_release.claim_released_run_still_held",
                run_id=str(run_id),
                blocking_causes=list(blocking),
            )
        else:
            _log.info("ratification_release.resumed", run_id=str(run_id))


def make_ratification_release_subscriber(deps: Kernel) -> RatificationReleaseSubscriber:
    """Build the RatificationRelease subscriber closed over the shared deps."""
    return RatificationReleaseSubscriber(
        event_store=deps.event_store,
        authz=deps.authz,
        clock=deps.clock,
        id_generator=deps.id_generator,
    )


__all__ = ["RatificationReleaseSubscriber", "make_ratification_release_subscriber"]
