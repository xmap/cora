"""Read repository for the Acquisition aggregate.

`load_acquisition(event_store, acquisition_id) -> Acquisition | None`
mirrors `load_dataset` / `load_decision` / `load_run` / etc. The
aggregate is terminal at genesis, so a load returns either the
single-event genesis state or None.

The stream id IS the `acquisition_id` itself (UUIDv7, globally unique
by construction; no uuid5 derivation). List / filter across
Acquisitions runs against `proj_data_acquisition_summary`, not this
single-aggregate read.
"""

from uuid import UUID

from cora.data.aggregates.acquisition.events import from_stored
from cora.data.aggregates.acquisition.evolver import fold
from cora.data.aggregates.acquisition.state import Acquisition
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Acquisition"


async def load_acquisition(event_store: EventStore, acquisition_id: UUID) -> Acquisition | None:
    """Load and fold an Acquisition's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, acquisition_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
