"""Read repository for the Assembly aggregate.

`load_assembly(event_store, assembly_id) -> Assembly | None` mirrors
`load_mount` / `load_frame` / `load_asset`. Used by update-style
commands (`version_assembly`, `deprecate_assembly`,
`instantiate_assembly`) that need to load + fold before deciding.
"""

from uuid import UUID

from cora.equipment.aggregates.assembly.events import from_stored
from cora.equipment.aggregates.assembly.evolver import fold
from cora.equipment.aggregates.assembly.state import Assembly
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Assembly"


async def load_assembly(event_store: EventStore, assembly_id: UUID) -> Assembly | None:
    """Load and fold an Assembly's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, assembly_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
