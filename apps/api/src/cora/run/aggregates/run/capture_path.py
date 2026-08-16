"""CapturePath vault: a witnessed Run's observed capture file path.

Mirrors the `actor_profile` / `ProfileStore` PATTERN (memory/project_pii_vault,
memory/project_pii_vault_implementation_design), not its code
organization (see "BC-internal" below for the deliberate divergence
there): a mutable side table, keyed by an identity the domain already
has (here, the Run's own `run_id`), holding a value that must never
reach an event payload because events are immutable and INSERT-only at
the role level, so personal data written there could never be erased.

## Why this exists

`RunWitnessRecorder` observes the areaDetector file plugin's own
`FullFileName_RBV` readback and, once it verifies the reading postdates
the Run's own BEGUN time, needs somewhere to put the result. 2-BM's
directory layout embeds `{UserLastName}-{ProposalNumber}`
(`tomoscan_2bm.py:474-477`), so the observed path is personal data by
construction; it goes here, never onto `RunCompleted` / `RunAborted`.

## BC-internal, like ObservationStore and FeedHeartbeatStore

Unlike `ProfileStore` (Kernel-level because Access BC AND Agent BC both
write to it), this store has exactly one BC. Per `wire.py`'s own
"BC-internal ObservationStore + FeedHeartbeatStore wiring" convention,
it is built locally in `wire_run(deps)` from `deps.pool` and surfaced on
the `RunHandlers` bundle (`RunHandlers.capture_path_store`), not
promoted to a `Kernel` field. `main.py`'s composition-root lifespan
(`RunWitnessRecorder`, which is outside the Run BC) reads it off
`app.state.run.capture_path_store`, the same route
`app.state.run.feed_heartbeat_store` already takes.

## Read path never redacts; write path never logs

Unlike `load_actor_display_name`'s tombstone (which fires on
*erasure*), `load_run_capture_path`'s fallback fires on *absence*
(never observed, or rejected by the dual-clock guard): there is no
erasure slice yet. The resolved value IS the real path: an operator
reads it specifically to locate the file for `ingest_scan`, so nothing
in this module redacts it. Redaction belongs to logs, exception text,
and `capture_watch_preflight`, never to this authorized read.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress only at module level for the
# adapter classes. The Protocol + dataclass + tombstone helper stay
# strictly typed for every caller above the boundary. Mirrors
# `run/aggregates/run/entries.py`'s identical suppress comment.

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import asyncpg

UNOBSERVED_CAPTURE_PATH = "<path not observed>"


@dataclass(frozen=True)
class CapturePath:
    """One row in the `run_capture_path` PII vault.

    `observed_at` is the substrate's own timestamp for the reading
    (`Measurement.produced_at`), carried through so a reader can see
    when the file plugin actually opened the file, distinct from
    `created_at` (when this row was written).
    """

    run_id: UUID
    observed_path: str = field(repr=False)
    """Personal data. `repr=False` so an accidental bare `_log.info(...,
    row=row)` or assertion-failure message renders this dataclass
    without it; deliberate defense-in-depth, not the primary guard
    (nothing should be logging a `CapturePath` at all)."""
    observed_at: datetime
    created_at: datetime
    updated_at: datetime


class CapturePathStore(Protocol):
    """Read / write access to the `run_capture_path` table.

    Deliberately no batch/`get_many` read: every consumer resolves
    exactly one `run_id` at a time (`get_run`'s route/tool, mirroring
    `get_actor`'s single-entity `load_actor_display_name`). `list_runs`
    (the bulk, cursor-paginated query) never touches this store at all;
    see `list_runs.bind`'s own docstring for why a batch method here
    would be an attractive nuisance toward reintroducing that mistake.

    Two implementors: `PostgresCapturePathStore` (production) and
    `InMemoryCapturePathStore` (tests / `app_env=test`). No `delete` /
    `scrub_and_delete` method yet: no erasure slice calls one (see this
    module's docstring); a future slice adds it alongside the SQL
    `DELETE` grant the init migration already carries.
    """

    async def upsert(
        self,
        *,
        run_id: UUID,
        observed_path: str,
        observed_at: datetime,
        created_at: datetime,
    ) -> None:
        """Insert a new row or overwrite an existing one for `run_id`.

        Idempotent on the run_id PK: `RunWitnessRecorder` calls this at
        most once per promotion (one terminal per Run), but retrying
        after a partial failure replays cleanly.
        """
        ...

    async def get(self, run_id: UUID) -> CapturePath | None:
        """Fetch a row by run_id; `None` when absent (never observed,
        rejected by the dual-clock guard, or recording disabled)."""
        ...


async def load_run_capture_path(store: CapturePathStore, run_id: UUID) -> str:
    """Resolve the observed path for a run_id; fallback when absent.

    Read-path convention mirroring `load_actor_display_name`: any
    handler surfacing this value calls this helper rather than
    inlining the `None` check. Returns `UNOBSERVED_CAPTURE_PATH` when
    no row exists, which the caller should treat as "not yet observed
    or rejected by the dual-clock guard," never as an error.
    """
    row = await store.get(run_id)
    return row.observed_path if row else UNOBSERVED_CAPTURE_PATH


_UPSERT_SQL = """
INSERT INTO run_capture_path (run_id, observed_path, observed_at, created_at, updated_at)
VALUES ($1, $2, $3, $4, $4)
ON CONFLICT (run_id) DO UPDATE
    SET observed_path = EXCLUDED.observed_path,
        observed_at = EXCLUDED.observed_at,
        updated_at = now()
"""

_GET_SQL = """
SELECT run_id, observed_path, observed_at, created_at, updated_at
FROM run_capture_path
WHERE run_id = $1
"""


def _row_to_capture_path(row: asyncpg.Record) -> CapturePath:
    return CapturePath(
        run_id=row["run_id"],
        observed_path=row["observed_path"],
        observed_at=row["observed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresCapturePathStore:
    """asyncpg-backed `CapturePathStore` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert(
        self,
        *,
        run_id: UUID,
        observed_path: str,
        observed_at: datetime,
        created_at: datetime,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(_UPSERT_SQL, run_id, observed_path, observed_at, created_at)

    async def get(self, run_id: UUID) -> CapturePath | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_GET_SQL, run_id)
        return _row_to_capture_path(row) if row is not None else None


class InMemoryCapturePathStore:
    """Test / `app_env=test` adapter for `CapturePathStore`.

    Postgres semantics preserved, mirroring `InMemoryProfileStore`:
    on insert, `updated_at = created_at` (the caller's clock read); on
    update, `updated_at = datetime.now(tz=UTC)` (the DB's own clock at
    `ON CONFLICT DO UPDATE` time in the real adapter's `_UPSERT_SQL`,
    never the caller-supplied `created_at`, which the real adapter
    never even sends on the UPDATE branch).
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, CapturePath] = {}

    async def upsert(
        self,
        *,
        run_id: UUID,
        observed_path: str,
        observed_at: datetime,
        created_at: datetime,
    ) -> None:
        existing = self._rows.get(run_id)
        if existing is None:
            self._rows[run_id] = CapturePath(
                run_id=run_id,
                observed_path=observed_path,
                observed_at=observed_at,
                created_at=created_at,
                updated_at=created_at,
            )
        else:
            self._rows[run_id] = CapturePath(
                run_id=run_id,
                observed_path=observed_path,
                observed_at=observed_at,
                created_at=existing.created_at,
                updated_at=datetime.now(tz=UTC),
            )

    async def get(self, run_id: UUID) -> CapturePath | None:
        return self._rows.get(run_id)


__all__ = [
    "UNOBSERVED_CAPTURE_PATH",
    "CapturePath",
    "CapturePathStore",
    "InMemoryCapturePathStore",
    "PostgresCapturePathStore",
    "load_run_capture_path",
]
