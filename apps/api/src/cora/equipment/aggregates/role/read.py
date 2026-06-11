"""Read repositories for the Role aggregate.

`load_role(event_store, role_id) -> Role | None` mirrors
`load_family` / `load_capability`. 3A ships the EventStore-replay
loader only; a projection-backed `load_role_timestamps` is not
present because Role has no FSM at 3A (single `RoleDefined` event;
no Versioned / Deprecated transitions to denormalize). When the
deferred Lock 14 versioning lands, the lifecycle-timestamps helper
joins this module alongside `load_role`.

Cross-aggregate existence checks (3B `add_family_presents_as`, 3D
`bind_plan_role`, 3E `update_capability_suggested_roles`) edge-load
via `Kernel.role_lookup.lookup` (the projection-backed RoleLookup
port), NOT an EventStore-replay helper. The projection is the
authoritative cross-aggregate read surface; bypassing it would
diverge from the established adapter pattern.

`_STREAM_TYPE = "Role"`. The stream-type string is the event store's
internal categorization key for this aggregate.
"""

from uuid import UUID

from cora.equipment.aggregates.role.events import from_stored
from cora.equipment.aggregates.role.evolver import fold
from cora.equipment.aggregates.role.state import Role
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Role"


async def load_role(event_store: EventStore, role_id: UUID) -> Role | None:
    """Load and fold a Role's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, role_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


__all__ = ["load_role"]
