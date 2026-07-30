"""The set of hold claims currently holding a Run: a fold, not a store.

`Run.status` answers "is this Run held". It cannot answer "by whom, and is
anyone else still holding it", because `HELD` is one bit. That was adequate
while a hold had a single author and became a safety fault once independent
governance concerns could each hold the same Run: a second holder arriving at
an already-held Run could not record its intent, and the FIRST holder's
release then resumed the Run with the second's cause unenforced.

This module is the missing half. `active_hold_claims` folds the Run's own event
stream into the set of claims not yet discharged. Nothing is stored: the claims
are derived from `RunHeld` / `HoldClaimReleased` / `RunResumed` on the same
authoritative stream every other Run projection reads, so a claim cannot drift
out of agreement with the events that created it, and no holder owes a
reconciled table.

## The release rule

A concern that placed a claim discharges it by folding first and then picking:

    claims = await active_hold_claims(event_store, run_id)
    if claims.keys() == {my_claim}:   # I am the last holder
        append RunResumed(released_claim_id=my_claim)
    elif my_claim in claims:          # others still hold it
        append HoldClaimReleased(claim_id=my_claim)
    else:                             # already discharged; nothing owed
        pass

`RunResumed` is legal only in the first branch. That is what makes the
transition to `RUNNING` mean "no concern is holding this Run" rather than
"whoever spoke last is done", and it is the property the deciders enforce.

## Legacy streams

A `RunHeld` written before holds were cause-scoped carries no `claim_id`. It
folds to the single `LEGACY_CLAIM_ID` claim, and a `RunResumed` with no
`released_claim_id` clears every active claim. Together those two rules replay
a pre-claim stream to exactly its old one-bit meaning, so this fold is additive
over history rather than a reinterpretation of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.run.aggregates.run.events import (
    LEGACY_CAUSE,
    LEGACY_CLAIM_ID,
    HoldClaimReleased,
    RunHeld,
    RunResumed,
)
from cora.run.aggregates.run.events import (
    from_stored as run_from_stored,
)

if TYPE_CHECKING:
    from cora.infrastructure.ports import EventStore
    from cora.infrastructure.ports.event_store import StoredEvent

RUN_STREAM_TYPE = "Run"

# Stable namespace for deriving a concern's claim id on a Run. Follows the
# subscriber convention of a fixed uuid5 namespace per derivation family.
_CLAIM_NAMESPACE = UUID("01900000-0000-7000-8000-00000000c1a1")


def derive_claim_id(run_id: UUID, cause: str) -> UUID:
    """The claim id a concern holds a given Run under: one claim per cause.

    Deterministic so a holder and a releaser agree on the id without either
    storing it, and so a re-delivered hold re-derives the same claim and folds
    idempotently rather than stacking a second one.

    ONE claim per (Run, cause) is a deliberate coarsening, and it is what the
    code already did: because every holder guarded `status is RUNNING`, a second
    request from the SAME concern on an already-held Run was a no-op, so two
    pending ratifications on one Run have always collapsed to one hold. Keeping
    that collapse means this change fixes the cross-cause fault without silently
    altering same-cause behaviour. Per-request claims (scoping ratification's
    claim by `ratification_id`) would be a further refinement and needs the
    release path to know which requests are still outstanding.
    """
    return uuid5(_CLAIM_NAMESPACE, f"{run_id}|{cause}")


def fold_hold_claims(events: list[object]) -> dict[UUID, str]:
    """Fold decoded Run events into `{claim_id: cause}` for undischarged claims.

    Insertion-ordered by when each claim was placed, so the oldest active claim
    reads first. Foreign event types are ignored rather than rejected: this is a
    projection over the Run stream, not the lifecycle evolver.
    """
    claims: dict[UUID, str] = {}
    for event in events:
        match event:
            case RunHeld(claim_id=claim_id, cause=cause):
                key = claim_id if claim_id is not None else LEGACY_CLAIM_ID
                # Re-holding under a live claim id is idempotent: the claim is
                # already active and its cause does not change. Re-holding after
                # a release legitimately re-places it.
                claims.setdefault(key, cause if cause is not None else LEGACY_CAUSE)
            case HoldClaimReleased(claim_id=claim_id):
                claims.pop(claim_id, None)
            case RunResumed(released_claim_id=released_claim_id):
                if released_claim_id is None:
                    # Legacy bare resume: the old one-bit semantics cleared the
                    # hold outright, so it clears every claim.
                    claims.clear()
                else:
                    claims.pop(released_claim_id, None)
            case _:
                continue
    return claims


def fold_hold_claims_from_stored(stored: list[StoredEvent]) -> dict[UUID, str]:
    """`fold_hold_claims` over raw stored events from one Run stream."""
    return fold_hold_claims([run_from_stored(s) for s in stored])


async def active_hold_claims(event_store: EventStore, run_id: UUID) -> dict[UUID, str]:
    """Load the Run stream and return its undischarged hold claims.

    Empty dict for a Run that was never held, whose holds are all discharged, or
    that does not exist. Callers that need the Run's status too should load once
    and use `fold_hold_claims_from_stored` rather than paying a second read.
    """
    stored, _ = await event_store.load(RUN_STREAM_TYPE, run_id)
    return fold_hold_claims_from_stored(stored)


def is_last_active_claim(claims: dict[UUID, str], claim_id: UUID) -> bool:
    """True when `claim_id` is active and is the ONLY active claim.

    The predicate that decides `RunResumed` vs `HoldClaimReleased`.
    """
    return set(claims) == {claim_id}


def blocking_causes(claims: dict[UUID, str], claim_id: UUID) -> tuple[str, ...]:
    """Causes of every active claim OTHER than `claim_id`, in claim order.

    What a refused resume reports back: naming the concerns that are still
    holding is the difference between "you cannot resume" and an operator having
    to guess which gate to go talk to.
    """
    return tuple(cause for cid, cause in claims.items() if cid != claim_id)


__all__ = [
    "RUN_STREAM_TYPE",
    "active_hold_claims",
    "blocking_causes",
    "derive_claim_id",
    "fold_hold_claims",
    "fold_hold_claims_from_stored",
    "is_last_active_claim",
]
