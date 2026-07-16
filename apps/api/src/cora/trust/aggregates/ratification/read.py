"""Load + fold a Ratification stream into current state.

The write-side load path used by the transition slices (grant / deny) to
reconstruct current state before deciding. Mirrors `load_visit`.
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.trust.aggregates.ratification.events import from_stored
from cora.trust.aggregates.ratification.evolver import fold
from cora.trust.aggregates.ratification.state import Ratification

_STREAM_TYPE = "Ratification"


async def load_ratification(event_store: EventStore, ratification_id: UUID) -> Ratification | None:
    """Load and fold a Ratification's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, ratification_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


__all__ = ["load_ratification"]
