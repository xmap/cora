"""Run-BC-local read port over one Run's full observation trail.

The `entries_run_observations` module has said since it was written that
"the range query for retrieval lands when a real consumer asks for it" and
left the table write-only from the application's perspective. This port is
that consumer: the `get_run_history` read slice needs every observation for
one Run, oldest first, to place on a scrubbable time axis.

## BC-local, not promoted to infrastructure/ports

Same reasoning as `run_channel_lookup.py`: the sole consumer today is
`get_run_history`, itself inside this BC. Promote only on a real second
cross-BC consumer.

## Ordered by recorded_at, not sampled_at

`recorded_at` is the Postgres write time and the trust anchor everywhere
else in this BC reads `entries_run_observations`; `sampled_at` is the
producer's phenomenonTime and is carried for display only. A scrubber
built on `sampled_at` would let a backfilled or clock-skewed producer
reorder the timeline; ordering on `recorded_at` cannot.

## Oldest-first, capped at limit

A scrubber needs a contiguous prefix from run start, not a tail: capping
at `limit` returns the OLDEST `limit` rows, never the newest. Callers that
need to know whether more exist fetch `limit + 1` and compare.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class RunObservationRow:
    """One row of a Run's observation trail, as read back for history.

    Mirrors `entries_run_observations` exactly. Exactly one of `value` /
    `categorical_value` is set per row, same exclusive arc as the write
    model's `Observation`."""

    event_id: UUID
    channel_name: str
    value: float | None
    categorical_value: str | None
    units: str | None
    sampling_procedure: str
    sampled_at: datetime
    occurred_at: datetime
    recorded_at: datetime
    is_simulated: bool


class RunObservationTrail(Protocol):
    """Read a Run's full observation trail, oldest first.

    Production adapter: `PostgresRunObservationTrail` (run/adapters/),
    reading `entries_run_observations` directly. Test adapter:
    `InMemoryRunObservationTrail`, reading through the same
    `InMemoryObservationStore` instance the write path uses.
    """

    async def read_run_observations(self, *, run_id: UUID, limit: int) -> list[RunObservationRow]:
        """Oldest `limit` observations for `run_id`, ordered
        `(recorded_at, event_id)`. Empty list if the run has none."""
        ...


__all__ = [
    "RunObservationRow",
    "RunObservationTrail",
]
