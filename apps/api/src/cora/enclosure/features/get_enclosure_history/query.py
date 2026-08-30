"""The `GetEnclosureHistory` query -- intent dataclass for this read slice."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetEnclosureHistory:
    """Read one enclosure's full exact-timestamped history: its own
    events, each with its own occurred_at / recorded_at. No `limit`
    field -- the cap is a handler constant, so the wire surface stays
    small and the response says whether it truncated. Mirrors
    `GetRunHistory`'s shape."""

    enclosure_id: UUID
