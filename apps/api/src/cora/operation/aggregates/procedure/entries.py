"""Activity entry: per-Procedure procedural step row.

Fourth concrete entry kind in CORA after `Verdict`,
`Inference`, and `Observation`. Same per-category
writer pattern: a typed dataclass + per-category Postgres adapter
alongside the owning aggregate, with a category-local `ActivityStore`
Protocol (NOT a shared cross-BC port).

## Storage shape: Path C in the cross-BC trichotomy

Per [[project_logbook_entry_storage]] §"The rule (the trichotomy)",
Activity sits at **Path C** (polymorphic table with discriminator
column + JSON-payload column):

  - **Path A** (typed sibling tables, one per kind) → Verdict,
    Inference. Pick when shape diverges AND per-kind volume /
    queryability matter.
  - **Path B** (polymorphic + typed value columns) → Observation. Pick
    when shape is uniform across kinds.
  - **Path C** (polymorphic + JSON payload) → Activity. Pick when
    shape diverges BUT per-kind volume is low / no per-kind read-side
    projection is planned.

Activity's body shape DIVERGES across kinds (setpoint =
channel + target_value + units? + ramp_rate?; action = action_name +
params; check = channel + passed + expected? + actual? + tolerance?),
so typed columns would mean lots of mostly-NULL per-kind columns. But
per-kind row volume at MVP scale is in the hundreds, and operator
queries don't filter by kind alone, so 3 sibling tables would be
overkill. JSON `payload` column with per-kind Pydantic validation at
the API layer is the right shape.

Standards precedent for Path C: OPC UA Part 10 §5.2.5-5.2.6 emits
SEPARATE events per program state transition (each transition has
its own audit event with transition-specific payload); Bluesky
event-model uses separate documents per phase (RunStart / Descriptor
/ Event / RunStop); 21 CFR Part 11 favors independent-action audit
records; modern event-sourcing consensus is JSON-payload-with-
discriminator over typed columns when per-kind shape evolves at code
speed.

## Logbook + Entry skeleton (shared with Observation + Inference + Verdict)

The body-shape encoding diverges from Observation, but the SKELETON is
identical: lazy open-on-first-write envelope event, three timestamps,
per-category `<EntryNoun>Store` port with InMemory + Postgres adapters,
dedicated `entries_<aggregate>_<entry_noun_plural>` table, batch
`Append<...>` slice. See [[project_logbook_entry_storage]] §"Naming
family (cross-BC)" for the full shape.

## Three timestamps

  - `sampled_at`: phenomenonTime -- when the step physically happened
    in the field (operator-recorded or instrument-clock; mandatory).
  - `occurred_at`: when the handler appended the entry (CORA Clock
    port; same convention as the events table and other entries).
  - `recorded_at`: when Postgres wrote the row (`DEFAULT now()`; same
    convention as the events table and other entries).

## Why writes batch from day one

`append(rows: list[Activity])` always takes a list. Operator
workflows often record several steps at once (an alignment
with 5 setpoints + 5 checks); batch shape avoids N round-trips. Empty
lists are a no-op.

## Why no read shape today

The retrieval query lands when a real consumer asks for it. Today the
table is write-only from the application's perspective; ad-hoc SQL
covers any operator queries. Same posture as the prior three entry
kinds.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress only at module level for the
# adapter class. The dataclass + Protocol stay strictly typed for
# every caller above the boundary.

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class Activity:
    """One row in the per-Procedure steps logbook.

    Polymorphic by `step_kind` (setpoint | action | check). All kinds
    share this row shape; the kind-specific body lives in `payload`
    (a JSON-serializable dict).

    `event_id` is the producer-assigned UUIDv7 identity (matches the
    existing event-sourcing convention). Used as the dedup key under
    at-least-once delivery; PRIMARY KEY at the table level handles the
    Postgres-side dedup. `correlation_id` and `causation_id` thread
    through from the originating command's envelope for full audit
    traceability.
    """

    event_id: UUID
    procedure_id: UUID
    logbook_id: UUID
    actor_id: UUID
    command_name: str
    step_kind: str
    payload: dict[str, Any]
    sampled_at: datetime
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID | None


class ActivityStore(Protocol):
    """Per-category port for Activity entry writes.

    The `append_activities` handler (and any future Procedure-side
    step writer, for example an EPICS adapter that auto-records a step
    per StepRecord PV update) takes a `ActivityStore` and calls
    `append(...)` per batch.

    Two implementations: `PostgresActivityStore` (production) and
    `InMemoryActivityStore` (tests / `app_env=test`). Both honor the same
    at-least-once contract: callers may retry the same `event_id`, the
    store dedups via the table's PK constraint (Postgres) or the
    in-memory dict (InMemory).
    """

    async def append(self, rows: list[Activity]) -> None: ...


_APPEND_SQL = """
INSERT INTO entries_operation_procedure_activities (
    event_id, procedure_id, logbook_id, actor_id, command_name,
    step_kind, payload, sampled_at, occurred_at, correlation_id, causation_id
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
ON CONFLICT (event_id) DO NOTHING
"""


class PostgresActivityStore:
    """asyncpg-backed `ActivityStore` implementation.

    Uses `ON CONFLICT (event_id) DO NOTHING` for idempotent retries:
    a producer that re-issues the same `event_id` (after a transient
    network failure on the previous attempt) is a no-op rather than
    a constraint violation. Matches the precedent set by
    `PostgresVerdictStore`, `PostgresInferenceStore`, and
    `PostgresObservationStore`.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, rows: list[Activity]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_SQL,
                [
                    (
                        row.event_id,
                        row.procedure_id,
                        row.logbook_id,
                        row.actor_id,
                        row.command_name,
                        row.step_kind,
                        # Pass the dict; the pool's jsonb codec (pool.py
                        # set_type_codec encoder=json.dumps) serializes it ONCE
                        # into a real jsonb OBJECT, exactly like the event store
                        # passes event.payload. An EXTRA json.dumps here (the
                        # former code) double-encoded it into a jsonb SCALAR
                        # string, which made server-side `payload->>'key'`
                        # return NULL and silently no-op'd the conductor's
                        # in-flight-marker filters. (The decision_inferences
                        # adapter still json.dumps-es into jsonb; harmless only
                        # while nothing queries its jsonb server-side.)
                        row.payload,
                        row.sampled_at,
                        row.occurred_at,
                        row.correlation_id,
                        row.causation_id,
                    )
                    for row in rows
                ],
            )


class InMemoryActivityStore:
    """Test / `app_env=test` adapter for `ActivityStore`.

    Dict keyed by `event_id` for trivial dedup. Exposes `all()` so
    contract / unit tests can assert what was emitted without going
    through Postgres.
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, Activity] = {}

    async def append(self, rows: list[Activity]) -> None:
        for row in rows:
            # ON CONFLICT DO NOTHING semantics: existing wins (matches
            # the Postgres adapter's behavior under retry).
            self._rows.setdefault(row.event_id, row)

    def all(self) -> list[Activity]:
        return list(self._rows.values())


__all__ = [
    "Activity",
    "ActivityStore",
    "InMemoryActivityStore",
    "PostgresActivityStore",
]
