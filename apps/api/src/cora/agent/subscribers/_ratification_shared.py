"""Shared helpers for the consequence-gate (Gate IV) enforcer subscribers.

Leading-underscore module: intra-package machinery, not a subscriber itself (the
`test_agent_subscribers_completeness` discovery skips `_`-prefixed files). Home for
what `ratification_hold.py` and `ratification_release.py` both need: the pinned
enforcer identity guard and this gate's hold-claim helpers.

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
from cora.run.aggregates.run import HOLD_CAUSE_RATIFICATION, derive_claim_id

if TYPE_CHECKING:
    from uuid import UUID

    from cora.infrastructure.ports import EventStore

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


def ratification_claim_id(run_id: UUID) -> UUID:
    """The claim id this gate holds `run_id` under.

    Derived, not stored, so hold and release agree without a lookup and a
    re-delivered hold re-derives the same claim instead of stacking a second.
    """
    return derive_claim_id(run_id, HOLD_CAUSE_RATIFICATION)


def enforcer_holds_claim(claims: dict[UUID, str], run_id: UUID) -> bool:
    """True iff this gate has an active hold claim on the run."""
    return ratification_claim_id(run_id) in claims


def others_still_holding(claims: dict[UUID, str], run_id: UUID) -> tuple[str, ...]:
    """Causes of every active claim on the run OTHER than this gate's.

    Non-empty means the release must discharge its own claim WITHOUT resuming:
    the run stays Held on behalf of whoever remains. This is the check that
    replaced scanning backward for the latest `RunHeld` and comparing its
    envelope principal. That scan answered "did I place the most recent hold",
    which is the right question only when holds cannot overlap; because every
    holder used to no-op on an already-held run, a hold arriving during this
    gate's co-signature wait left no event at all and the scan could not see it.
    """
    own = ratification_claim_id(run_id)
    return tuple(cause for claim_id, cause in claims.items() if claim_id != own)


__all__ = [
    "HOLD_COMMAND_NAME",
    "RESUME_COMMAND_NAME",
    "RUN_STREAM_TYPE",
    "enforcer_holds_claim",
    "enforcer_standing_down",
    "others_still_holding",
    "ratification_claim_id",
]
