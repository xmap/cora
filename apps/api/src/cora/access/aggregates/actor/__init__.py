"""Actor aggregate: state, errors, events, evolver, profile (PII vault).

Vertical slices that operate on this aggregate live under
`cora.access.features.<verb>_actor/` and import from here for state,
event, and profile types.
"""

from cora.access.aggregates.actor.events import (
    ActorDeactivated,
    ActorEvent,
    ActorProfileForgotten,
    ActorReactivated,
    ActorRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.access.aggregates.actor.evolver import evolve, fold
from cora.access.aggregates.actor.profile import (
    DELETED_ACTOR_DISPLAY_NAME,
    Profile,
    ProfileStore,
    load_actor_display_name,
)
from cora.access.aggregates.actor.read import load_actor
from cora.access.aggregates.actor.state import (
    ACTOR_NAME_MAX_LENGTH,
    Actor,
    ActorAlreadyExistsError,
    ActorCannotDeactivateError,
    ActorCannotReactivateError,
    ActorKind,
    ActorName,
    ActorNotFoundError,
    InvalidActorKindError,
    InvalidActorNameError,
)

# Adapters live in `cora.infrastructure.{memory,postgres}.profile_store`
# (mirroring EventStore + IdempotencyStore placement); re-exported here
# so existing imports of
# `from cora.access.aggregates.actor import InMemoryProfileStore` keep
# working.
from cora.infrastructure.adapters.in_memory_profile_store import InMemoryProfileStore
from cora.infrastructure.adapters.postgres_profile_store import PostgresProfileStore

__all__ = [
    "ACTOR_NAME_MAX_LENGTH",
    "DELETED_ACTOR_DISPLAY_NAME",
    "Actor",
    "ActorAlreadyExistsError",
    "ActorCannotDeactivateError",
    "ActorCannotReactivateError",
    "ActorDeactivated",
    "ActorEvent",
    "ActorKind",
    "ActorName",
    "ActorNotFoundError",
    "ActorProfileForgotten",
    "ActorReactivated",
    "ActorRegistered",
    "InMemoryProfileStore",
    "InvalidActorKindError",
    "InvalidActorNameError",
    "PostgresProfileStore",
    "Profile",
    "ProfileStore",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_actor",
    "load_actor_display_name",
    "to_payload",
]
