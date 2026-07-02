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


@dataclass(frozen=True)
class Diagnostic:
    """One row in the per-Procedure GP-steering diagnostics logbook.

    Fifth concrete entry kind (after `Verdict`, `Inference`, `Observation`,
    `Activity`), and the second on the Procedure aggregate. It records, per
    steered-conduct iteration decided by a learning brain, the fitted model's
    summary scalars (per-axis lengthscales, observation noise, acquisition
    value) so a reviewer can answer "why did the brain advise that point"
    after the run. Path C (polymorphic JSON payload): the scalar set diverges
    by brain / model, per-row volume is low (one row per steered iteration),
    and no per-kind read-side projection is planned, so a single `payload`
    jsonb column beats typed sibling columns. Mirrors the `Activity` skeleton
    in this same aggregate.

    `iteration_index` links the row to the steered pass it explains (the same
    `iteration_index` carried on `ProcedureIterationEnded`), so an auditor can
    join a diagnostic row to the decision it justified. `model_ref` is the
    deciding brain's ref (`botorch`), mirroring the iteration event. The
    optimizer-specific scalar names live only as keys inside `payload`, never
    as columns or identifiers, keeping optimizer vocabulary out of the schema.

    `event_id` is the producer-assigned UUIDv7 identity, the dedup key under
    at-least-once delivery (table PRIMARY KEY). `correlation_id` /
    `causation_id` thread from the originating command's envelope.
    """

    event_id: UUID
    procedure_id: UUID
    logbook_id: UUID
    iteration_index: int
    model_ref: str
    payload: dict[str, Any]
    sampled_at: datetime
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID | None


class DiagnosticStore(Protocol):
    """Per-category port for Diagnostic entry writes.

    The `append_diagnostics` handler takes a `DiagnosticStore` and calls
    `append(...)` per batch. Two implementations: `PostgresDiagnosticStore`
    (production) and `InMemoryDiagnosticStore` (tests / `app_env=test`). Both
    honor at-least-once: callers may retry the same `event_id`; the store
    dedups via the table PK (Postgres) or the in-memory dict (InMemory).
    """

    async def append(self, rows: list[Diagnostic]) -> None: ...


_APPEND_DIAGNOSTICS_SQL = """
INSERT INTO entries_operation_procedure_diagnostics (
    event_id, procedure_id, logbook_id, iteration_index, model_ref,
    payload, sampled_at, occurred_at, correlation_id, causation_id
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (event_id) DO NOTHING
"""


class PostgresDiagnosticStore:
    """asyncpg-backed `DiagnosticStore` implementation.

    `ON CONFLICT (event_id) DO NOTHING` for idempotent retries, matching
    `PostgresActivityStore` / `PostgresInferenceStore`. `payload` is passed
    as a dict; the pool's jsonb codec (`pool.py` set_type_codec
    encoder=json.dumps) serializes it once into a real jsonb OBJECT, exactly
    like `PostgresActivityStore` (NO extra json.dumps, which would double-
    encode into a jsonb scalar string).
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, rows: list[Diagnostic]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_DIAGNOSTICS_SQL,
                [
                    (
                        row.event_id,
                        row.procedure_id,
                        row.logbook_id,
                        row.iteration_index,
                        row.model_ref,
                        row.payload,
                        row.sampled_at,
                        row.occurred_at,
                        row.correlation_id,
                        row.causation_id,
                    )
                    for row in rows
                ],
            )


class InMemoryDiagnosticStore:
    """Test / `app_env=test` adapter for `DiagnosticStore`.

    Dict keyed by `event_id` for trivial dedup. Exposes `all()` so tests can
    assert what was emitted without going through Postgres.
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, Diagnostic] = {}

    async def append(self, rows: list[Diagnostic]) -> None:
        for row in rows:
            self._rows.setdefault(row.event_id, row)

    def all(self) -> list[Diagnostic]:
        return list(self._rows.values())


@dataclass(frozen=True)
class Outcome:
    """One row in the per-Procedure steered-pass outcome logbook.

    Sixth concrete entry kind (after `Verdict`, `Inference`, `Observation`,
    `Activity`, `Diagnostic`), and the third on the Procedure aggregate. It
    records, per steered-conduct pass, the SELF-DESCRIBING observation the brain
    fit against: the coordinate it measured at (`point`, the "x") AND the
    measured values there (`measurements`, the "y"). Its purpose is RESUME: on
    restart of a crashed GP-steered run, the optimizer's observation history is
    rebuilt directly from these rows instead of re-measuring hardware. Distinct
    from `Diagnostic` (the fitted model's internal scalars) and `Activity` (the
    physical steps): this is the observed result of a pass.

    ## Self-describing: point + measurements in one row

    An early design recorded only `measurements` and recovered the point by a
    POSITIONAL join to `ProcedureIterationEnded.advised_next_point` (outcome k
    paired to the prior pass's advice). That join broke after an abandoned pass
    (a mid-pass crash inserts an extra iteration event, permanently drifting the
    0-based outcome ordinal from the 1-based iteration index). Carrying `point`
    on the row removes the join entirely: reconstruction is sort-by-index then
    map, and index gaps left by abandoned passes are harmless (a sort preserves
    order regardless of gaps). No off-by-one, no gap-free precondition.

    Path C (polymorphic JSON payload): `measurements` is a list of Measurement
    dicts (value / kind / quality / name / units) and `point` is a coordinate
    map, both of beamline-varying shape, so single jsonb columns beat typed
    sibling columns; per-row volume is low (one row per steered pass). Mirrors
    the `Diagnostic` skeleton in this same aggregate.

    `iteration_index` is the ORDERING key for reconstruction (ascending = pass
    order) and an audit cross-reference to the FSM iteration that produced the
    row; it is 0-based and may have gaps after an abandoned pass, which the
    sort-then-map reconstruction tolerates. `succeeded` mirrors the
    SteeringObservation success flag (a failed acquisition is a real datum);
    `actuation_kind` threads the Physical / Simulated / Hybrid provenance so a
    resumed fit can distrust a simulated outcome.

    `event_id` is the producer-assigned UUIDv7 identity, the dedup key under
    at-least-once delivery (table PRIMARY KEY). `correlation_id` /
    `causation_id` thread from the originating command's envelope.
    """

    event_id: UUID
    procedure_id: UUID
    logbook_id: UUID
    iteration_index: int
    point: dict[str, Any]
    measurements: list[dict[str, Any]]
    succeeded: bool
    actuation_kind: str | None
    sampled_at: datetime
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID | None


class OutcomeStore(Protocol):
    """Per-category port for Outcome entry writes.

    The `append_outcomes` handler takes an `OutcomeStore` and calls
    `append(...)` per batch. Two implementations: `PostgresOutcomeStore`
    (production) and `InMemoryOutcomeStore` (tests / `app_env=test`). Both
    honor at-least-once: callers may retry the same `event_id`; the store
    dedups via the table PK (Postgres) or the in-memory dict (InMemory).
    """

    async def append(self, rows: list[Outcome]) -> None: ...


_APPEND_OUTCOMES_SQL = """
INSERT INTO entries_operation_procedure_outcomes (
    event_id, procedure_id, logbook_id, iteration_index, point, measurements,
    succeeded, actuation_kind, sampled_at, occurred_at, correlation_id, causation_id
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
ON CONFLICT (event_id) DO NOTHING
"""


class PostgresOutcomeStore:
    """asyncpg-backed `OutcomeStore` implementation.

    `ON CONFLICT (event_id) DO NOTHING` for idempotent retries, matching
    `PostgresDiagnosticStore` / `PostgresActivityStore`. `measurements` is
    passed as a list; the pool's jsonb codec (`pool.py` set_type_codec
    encoder=json.dumps) serializes it once into a real jsonb array, exactly
    like `PostgresActivityStore` passes its payload dict (NO extra json.dumps,
    which would double-encode into a jsonb scalar string).
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, rows: list[Outcome]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_OUTCOMES_SQL,
                [
                    (
                        row.event_id,
                        row.procedure_id,
                        row.logbook_id,
                        row.iteration_index,
                        row.point,
                        row.measurements,
                        row.succeeded,
                        row.actuation_kind,
                        row.sampled_at,
                        row.occurred_at,
                        row.correlation_id,
                        row.causation_id,
                    )
                    for row in rows
                ],
            )


class InMemoryOutcomeStore:
    """Test / `app_env=test` adapter for `OutcomeStore`.

    Dict keyed by `event_id` for trivial dedup. Exposes `all()` so tests can
    assert what was emitted without going through Postgres, and
    `for_procedure(...)` so the resume-time in-memory outcome-lookup adapter can
    read back a procedure's outcomes (the aggregate layer must not depend on the
    ports layer, so the `ProcedureOutcomeLookup`-shaped read wrapper lives in
    `operation/adapters/`, not here).
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, Outcome] = {}

    async def append(self, rows: list[Outcome]) -> None:
        for row in rows:
            self._rows.setdefault(row.event_id, row)

    def all(self) -> list[Outcome]:
        return list(self._rows.values())

    def for_procedure(self, procedure_id: UUID) -> list[Outcome]:
        """Return a procedure's recorded outcomes, ascending by iteration_index."""
        rows = [row for row in self._rows.values() if row.procedure_id == procedure_id]
        rows.sort(key=lambda row: row.iteration_index)
        return rows


__all__ = [
    "Activity",
    "ActivityStore",
    "Diagnostic",
    "DiagnosticStore",
    "InMemoryActivityStore",
    "InMemoryDiagnosticStore",
    "InMemoryOutcomeStore",
    "Outcome",
    "OutcomeStore",
    "PostgresActivityStore",
    "PostgresDiagnosticStore",
    "PostgresOutcomeStore",
]
