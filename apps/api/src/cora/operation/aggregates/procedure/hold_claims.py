"""Deriving the claim id a concern holds a Procedure under.

The claim SET itself is folded onto `Procedure.hold_claims` by the evolver, so
a decider that already has folded state needs no second read. This module holds
only the derivation, which both a holder and a releaser must agree on without
either storing the id.

Deliberately smaller than Run's sibling module, which also folds claims straight
from the event store. Run needs that because concerns OUTSIDE its BC hold Runs
and cannot fold the aggregate. Every Procedure holder today is the Conductor or
an operator surface, all of which go through a decider that receives folded
state. Add the event-store fold when an out-of-BC holder actually appears.
"""

from __future__ import annotations

from uuid import UUID, uuid5

# Stable namespace for deriving a concern's claim id on a Procedure. Distinct
# from Run's namespace so the two aggregates cannot collide, following the
# fixed-uuid5-namespace-per-derivation-family convention.
_CLAIM_NAMESPACE = UUID("01900000-0000-7000-8000-00000000c1a2")


def derive_claim_id(procedure_id: UUID, cause: str) -> UUID:
    """The claim id a concern holds a given Procedure under: one per cause.

    Deterministic so a holder and a releaser agree without either storing it,
    and so a re-delivered hold re-derives the same claim and folds idempotently
    rather than stacking a second one.

    ONE claim per (Procedure, cause) is a deliberate coarsening, and it is what
    the code already did: because every holder guarded `status is RUNNING`, a
    second request from the SAME concern on an already-held Procedure was
    refused outright. Keeping that collapse means this change fixes the
    cross-cause fault without silently altering same-cause behaviour. Scoping a
    claim more finely (per failing step, say) is a further refinement and would
    need the release path to know which of them are still outstanding.
    """
    return uuid5(_CLAIM_NAMESPACE, f"{procedure_id}|{cause}")


__all__ = ["derive_claim_id"]
