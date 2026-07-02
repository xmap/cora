"""Run-BC-local read port over the actor -> in-flight-runs index.

Answers the one question the authority-revocation kill-switch asks: given
an actor whose grant was just revoked, which runs is that actor behind
that are still in flight (Running or Held) and therefore need to be held?
"Behind" spans both involvement kinds recorded in
`proj_run_actor_involvement`: runs the actor STARTED and runs the actor
SUPERVISES.

## BC-local, not promoted to infrastructure/ports

Mirrors the `RunChannelLookup` precedent: the sole consumer is the
composition-root compensation subscriber (Slice 3), which already imports
Run-BC symbols directly, and the data-owning projection is Run-BC-internal.
Promote to `infrastructure/ports/` only on a real second cross-BC consumer
(rule-of-three).

## Distinct run_ids, involvement-kind-agnostic

The lookup returns a set of run_ids, deduplicated across involvement
kinds: an actor who both started AND supervises the same run yields that
run once. The caller holds a run, not a (run, kind) pair, so the kind is
irrelevant at the read boundary.
"""

from typing import Protocol
from uuid import UUID


class RunActorInvolvementLookup(Protocol):
    """Read the actor -> in-flight-runs index for the kill-switch.

    Production adapter: `PostgresRunActorInvolvementLookup` (run/adapters/),
    backed by `proj_run_actor_involvement`.
    """

    async def find_inflight_run_ids(self, actor_id: UUID) -> frozenset[UUID]:
        """Distinct ids of runs the actor is behind (started or
        supervises) that are still Running or Held. Empty when the actor
        is behind no in-flight run."""
        ...


class InMemoryRunActorInvolvementLookup:
    """Dict-backed, seedable `RunActorInvolvementLookup` for unit tests.

    An unseeded instance returns the empty set for every actor. Seed via
    `register(actor_id, run_id)` to make that run appear as in-flight for
    that actor; `register` is involvement-kind-agnostic (the read is), so
    tests express only "this actor is behind this in-flight run".
    """

    def __init__(self) -> None:
        self._by_actor: dict[UUID, set[UUID]] = {}

    def register(self, *, actor_id: UUID, run_id: UUID) -> None:
        self._by_actor.setdefault(actor_id, set()).add(run_id)

    async def find_inflight_run_ids(self, actor_id: UUID) -> frozenset[UUID]:
        return frozenset(self._by_actor.get(actor_id, set()))


__all__ = [
    "InMemoryRunActorInvolvementLookup",
    "RunActorInvolvementLookup",
]
