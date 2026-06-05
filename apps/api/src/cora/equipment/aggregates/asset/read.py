"""Read repository for the Asset aggregate.

`load_asset(event_store, asset_id) -> Asset | None` mirrors
`load_family` / `load_subject` / `load_actor`. Used by the
`get_asset` query slice and any future update-style commands.

`load_partition_rule(event_store, asset_id) -> PartitionRule | None`
is a convenience accessor for the PseudoAxis pattern; it returns
None for Assets that are not of Family PseudoAxis AND for PseudoAxis
Assets whose rule has not been set yet. See [[project-pseudoaxis-design]] v3.
"""

from uuid import UUID

from cora.equipment.aggregates._partition_rule import PartitionRule
from cora.equipment.aggregates.asset.events import from_stored
from cora.equipment.aggregates.asset.evolver import fold
from cora.equipment.aggregates.asset.state import Asset
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Asset"


async def load_asset(event_store: EventStore, asset_id: UUID) -> Asset | None:
    """Load and fold an Asset's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, asset_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_partition_rule(event_store: EventStore, asset_id: UUID) -> PartitionRule | None:
    """Convenience accessor for the PseudoAxis pattern.

    Returns the Asset's current `partition_rule` if any. Returns None
    for Assets that do not exist, Assets that are not of Family
    PseudoAxis, AND PseudoAxis Assets whose rule has not been set yet.
    Callers that need to distinguish these cases load the Asset via
    `load_asset` and inspect state directly.
    """
    state = await load_asset(event_store, asset_id)
    if state is None:
        return None
    return state.partition_rule
