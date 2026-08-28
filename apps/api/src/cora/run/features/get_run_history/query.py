"""The `GetRunHistory` query -- intent dataclass for this read slice."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetRunHistory:
    """Read one run's full exact-timestamped history: its own events plus
    its observation trail. No `limit` field -- the cap on observations is
    a handler constant, so the wire surface stays as small as `GetRun`'s
    and the response says whether it truncated."""

    run_id: UUID
