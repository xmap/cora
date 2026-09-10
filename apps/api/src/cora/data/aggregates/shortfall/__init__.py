"""Shortfall aggregate: state, status/reason enums, events, evolver, read repo.

The Shortfall is a slim recorded-fact-chain in the Data BC: the fact
that a capture produced something that can never become a Dataset.
Terminal at genesis, one stream per `capture_path_id`, exactly one
`ShortfallRecorded` event ever.

No vertical slice of its own. Unlike `Acquisition`, which the
`record_acquisition` slice owns, a Shortfall is appended from the
EXISTING `ingest_scan` slice as its second outcome: the frame counts
that make the fact worth recording are computed by the same reader
pass that refuses the file, and a separate command would need its own
grant, route and MCP tool to record a fact no human asks for. See
`cora.data.features.ingest_scan.handler` for the append site and
`_stream_id.py` for why the stream id is derived.
"""

from cora.data.aggregates.shortfall._stream_id import shortfall_stream_id
from cora.data.aggregates.shortfall.events import (
    ShortfallEvent,
    ShortfallRecorded,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.data.aggregates.shortfall.evolver import evolve, fold
from cora.data.aggregates.shortfall.read import load_shortfall
from cora.data.aggregates.shortfall.state import (
    Shortfall,
    ShortfallReason,
    ShortfallStatus,
)

__all__ = [
    "Shortfall",
    "ShortfallEvent",
    "ShortfallReason",
    "ShortfallRecorded",
    "ShortfallStatus",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_shortfall",
    "shortfall_stream_id",
    "to_payload",
]
