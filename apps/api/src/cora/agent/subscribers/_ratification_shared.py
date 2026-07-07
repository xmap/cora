"""Shared helpers for the consequence-gate (Gate IV) enforcer subscribers.

Leading-underscore module: intra-package machinery, not a subscriber itself (the
`test_agent_subscribers_completeness` discovery skips `_`-prefixed files). Home for
what `ratification_hold.py` and `ratification_release.py` both need: the pinned
enforcer identity guard and the hold-correlation guard.

The two subscribers, acting as the pinned RatificationEnforcer agent, turn the
consequence gate's refuse-and-park flow into real RunHeld / RunResumed transitions
on the SAME shared hold the kill-switch uses. Both write via Pattern C (load,
guard status in-process, authorize as their own principal, append from
cora.run.aggregates), because cora.agent may depend on cora.run.aggregates +
cora.trust.aggregates but NOT cora.run.features (the tach BC boundary). Neither
writes a Decision: the Ratification events (Requested/Granted/Denied) are the
provenance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_ratification_enforcer import RATIFICATION_ENFORCER_AGENT_ID

if TYPE_CHECKING:
    from cora.infrastructure.ports import EventStore
    from cora.infrastructure.ports.event_store import StoredEvent

RUN_STREAM_TYPE = "Run"
HOLD_COMMAND_NAME = "HoldRun"
RESUME_COMMAND_NAME = "ResumeRun"


async def enforcer_standing_down(event_store: EventStore) -> bool:
    """True if the enforcer is not seeded yet or was operator-deactivated.

    Same operator-deactivation revocation surface every sibling agent uses
    (load_actor().active): an operator disables the gate the same way they disable
    any agent.
    """
    actor = await load_actor(event_store, RATIFICATION_ENFORCER_AGENT_ID)
    return actor is None or not actor.active


def last_hold_placed_by_enforcer(stored: list[StoredEvent]) -> bool:
    """True iff the run's most-recent RunHeld was placed by this enforcer.

    The load-bearing correlation guard for the release: `RunStatus.HELD` is a
    single bit with no hold-source, so a run may be Held by the kill-switch, an
    operator, or this gate. Scanning backward for the latest RunHeld and checking
    its envelope principal_id lets the release resume ONLY a hold it placed, so a
    stray Granted/Denied cannot defeat a foreign hold (e.g. the kill-switch's).
    Returns False when no RunHeld exists (defensive; callers confirm status==HELD).
    """
    for event in reversed(stored):
        if event.event_type == "RunHeld":
            return event.principal_id == RATIFICATION_ENFORCER_AGENT_ID
    return False


__all__ = [
    "HOLD_COMMAND_NAME",
    "RESUME_COMMAND_NAME",
    "RUN_STREAM_TYPE",
    "enforcer_standing_down",
    "last_hold_placed_by_enforcer",
]
