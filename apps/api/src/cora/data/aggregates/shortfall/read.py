"""Read repository for the Shortfall aggregate.

`load_shortfall(event_store, shortfall_id) -> Shortfall | None` mirrors
`load_acquisition` / `load_attestation` / `load_dataset` / etc. The
aggregate is terminal at genesis, so a load returns either the
single-event genesis state or None.

Unlike `Acquisition`, the stream id is NOT a freshly minted UUIDv7: it
is derived from `capture_path_id` via `shortfall_stream_id`, so a
caller holding a vault row's surrogate key can address the stream
without a lookup. See `_stream_id.py` for why the derivation is
load-bearing rather than a convenience. List / filter across Shortfalls
runs against `proj_data_shortfall_summary`, not this single-aggregate
read.
"""

from uuid import UUID

from cora.data.aggregates.shortfall.events import from_stored
from cora.data.aggregates.shortfall.evolver import fold
from cora.data.aggregates.shortfall.state import Shortfall
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Shortfall"


async def load_shortfall(event_store: EventStore, shortfall_id: UUID) -> Shortfall | None:
    """Load and fold a Shortfall's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, shortfall_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
