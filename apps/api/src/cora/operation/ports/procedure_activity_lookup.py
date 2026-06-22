"""Operation-BC-local read port over a Procedure's append-only activity log.

The read half a watcher needs that the write side does not provide. The
activity entries written by `append_activities` land in
`entries_operation_procedure_activities` via a write-only `ActivityStore`,
and the procedure aggregate stream carries only the one-time
`ProcedureActivitiesLogbookOpened` marker, not per-activity recency. So
"when did this procedure last log activity" has no existing read path.

## Why it exists: the ProcedureWatcher anti-false-flag fold

ProcedureWatcher flags a Running / Held procedure that has sat past an
operator window without progressing, keyed on
`proj_operation_procedure_summary.last_status_changed_at`. But appending
activity steps does NOT advance that timestamp: the projection touches
`last_status_changed_at` only on real lifecycle transitions and NO-OPs it
for `ProcedureActivitiesLogbookOpened` / `ProcedureIterationStarted`
(activity is orthogonal to lifecycle). So a Running procedure actively
logging steps for hours looks frozen by its status timestamp alone.
Keying on it without folding in activity recency would FALSE-FLAG an
actively-progressing conduct, a foolable watchdog that is worse than
none. This read returns the newest activity `recorded_at` so the watcher
folds it in before flagging, exactly as ClearanceWatcher folds the latest
ReviewStep.decided_at for an UnderReview clearance.

## BC-local, not promoted to infrastructure/ports

The sole consumer is the composition-root ProcedureWatcher, which already
imports Operation-BC symbols directly; the data-owning sibling
`ActivityStore` is itself BC-internal. So this read counterpart lives
beside the BC, mirroring the RunChannelLookup single-root-consumer
precedent. Promote to `infrastructure/ports/` only on a real second
cross-BC consumer (rule-of-three).

## recorded_at is the trust anchor, not sampled_at

`recorded_at` is the Postgres write time (`DEFAULT now()`, CORA-owned);
`sampled_at` is the producer's phenomenonTime and is spoofable /
backfillable. The anti-false-flag fold keys on `recorded_at` so a
producer cannot backdate an entry to make a stalled conduct look active.
This mirrors RunChannelLookup keying freshness on `recorded_at`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ProcedureActivityRecency:
    """Newest activity recorded_at for one Procedure (the anti-false-flag fold).

    `latest_recorded_at` is None exactly when the procedure has never
    logged an activity entry: the cannot-tell case in which the watcher
    keeps the status timestamp as the staleness clock. Wrapped in a
    dataclass rather than a bare `datetime | None` for parity with
    RunFeedHealth and so a future field (e.g. an arrival count) can land
    additively.
    """

    latest_recorded_at: datetime | None


class ProcedureActivityLookup(Protocol):
    """Read a Procedure's append-only activity log for the liveness fold.

    One method: the newest activity `recorded_at`. Production adapter:
    `PostgresProcedureActivityLookup` (operation/adapters/), backed by
    querying the existing `entries_operation_procedure_activities` table.
    """

    async def read_procedure_activity_recency(
        self, *, procedure_id: UUID
    ) -> ProcedureActivityRecency:
        """Newest activity `recorded_at` for `procedure_id`; latest_recorded_at
        is None when the procedure has never logged an activity entry."""
        ...


class InMemoryProcedureActivityLookup:
    """Dict-backed, seedable `ProcedureActivityLookup` for unit tests.

    An unseeded instance is the always-quiet default: reads return a None
    recency, so the watcher tick is testable with no activity recorded.
    Seeded via `register(...)`, which carries an explicit `recorded_at`
    (the read surfaces recorded_at, which the write-model activity entry
    does not expose to the watcher).
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, list[datetime]] = {}

    def register(self, *, procedure_id: UUID, recorded_at: datetime) -> None:
        self._rows.setdefault(procedure_id, []).append(recorded_at)

    async def read_procedure_activity_recency(
        self, *, procedure_id: UUID
    ) -> ProcedureActivityRecency:
        rows = self._rows.get(procedure_id)
        return ProcedureActivityRecency(latest_recorded_at=max(rows) if rows else None)


__all__ = [
    "InMemoryProcedureActivityLookup",
    "ProcedureActivityLookup",
    "ProcedureActivityRecency",
]
