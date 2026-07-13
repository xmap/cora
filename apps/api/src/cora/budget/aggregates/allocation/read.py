"""Read repository for the Allocation aggregate.

`load_allocation(event_store, allocation_id) -> Allocation | None`
mirrors `load_language_model` / `load_campaign`. Used by the
update-style handlers (activate / amend / seal / void load the target
envelope before the decider) and by the grant handler's
caller-supplied-id collision check.
"""

from uuid import UUID

from cora.budget.aggregates.allocation.events import from_stored
from cora.budget.aggregates.allocation.evolver import fold
from cora.budget.aggregates.allocation.state import Allocation
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Allocation"


async def load_allocation(event_store: EventStore, allocation_id: UUID) -> Allocation | None:
    """Load and fold an Allocation's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, allocation_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
