"""EventStorePrincipalLivenessLookup: resolve liveness from the Actor stream.

Reads through `load_actor`, the same fold every seeded agent already
uses to check its own operator-deactivation switch
(`agent/subscribers/_ratification_shared.py`). Using the identical
surface for the gate is the point: one fact, one reader, so a human and
an agent cannot drift apart on it.

## Why the event store and not `proj_access_actor_summary`

The projection carries a `status` column and would be one indexed row
instead of a fold, which is cheaper. It is refused anyway, because a
projection lags: a principal deactivated a moment ago would keep
reading `active` for as long as the worker is behind, and the whole
value of this lookup is that turning someone off takes effect. A
revocation surface that is eventually consistent is a revocation
surface with a window in it.

The cost is bounded in a way it would not be for a larger aggregate:
an Actor stream is `ActorRegistered` plus at most a handful of
deactivate / reactivate / forget events, so the fold is a short read of
a stream that is small by construction.
"""

from uuid import UUID

from cora.access.aggregates.actor import load_actor
from cora.infrastructure.ports.event_store import EventStore
from cora.infrastructure.ports.principal_liveness_lookup import PrincipalLiveness


class EventStorePrincipalLivenessLookup:
    """Resolve `PrincipalLiveness` by folding the principal's Actor stream."""

    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    async def liveness_of(self, principal_id: UUID) -> PrincipalLiveness:
        """Fold the Actor stream for `principal_id` into a liveness value.

        A principal id IS an Actor id: `register_actor` mints the Actor
        whose id humans authenticate as, and `define_agent` writes the
        agent's Actor at the same id in one transaction. So no mapping
        step is needed here, and a missing stream means the principal
        was never registered rather than that the lookup failed.
        """
        actor = await load_actor(self._event_store, principal_id)
        if actor is None:
            return PrincipalLiveness.UNREGISTERED
        return PrincipalLiveness.ACTIVE if actor.active else PrincipalLiveness.DEACTIVATED


__all__ = ["EventStorePrincipalLivenessLookup"]
