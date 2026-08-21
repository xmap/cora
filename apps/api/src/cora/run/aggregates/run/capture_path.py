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
from uuid import UUID, uuid4

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

    capture_path_id: UUID
    """Surrogate key. Carried so the ordering in `get_latest` can be
    made TOTAL and identical in both adapters: without a final
    tiebreak, a full `(observed_at, updated_at)` tie resolves to the
    first-inserted row in memory and to whatever the planner returns in
    Postgres, which is not stable (the real plan sorts with quicksort)."""

    run_id: UUID
    observed_path: str = field(repr=False)
    """Personal data. `repr=False` so an accidental bare `_log.info(...,
    row=row)` or assertion-failure message renders this dataclass
    without it; deliberate defense-in-depth, not the primary guard
    (nothing should be logging a `CapturePath` at all)."""
    observed_at: datetime
    created_at: datetime
    updated_at: datetime
    host: str | None = None
    root: str | None = None
    """Where the path was observed, recorded at observation time and
    never re-derived from current settings. `None` on rows written
    before the vault tracked location, and on rows whose observed path
    matched no configured root (the same condition under which
    `mint_capture_path_locator` refuses). Not personal data: the tier
    is a facility-level directory, which is exactly why the locator can
    carry it in the clear while the rest of the path stays here."""


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
        host: str | None,
        root: str | None,
    ) -> None:
        """Insert a new row, or overwrite the one for this exact
        (run_id, host, root).

        Idempotent per LOCATION, not per Run: re-observing the same
        file on the same tier replays cleanly, while observing the same
        Run's file on a DIFFERENT tier adds a row rather than
        destroying the first. That distinction is the whole point of
        the location columns; see the migration's own comment for what
        the old run_id-keyed upsert would have done to an already
        minted locator.

        `observed_at` is the EPICS PV's own timestamp, not CORA's
        clock, so it can arrive out of order (a monitor reconnect
        replays a stale value, or an IOC's clock steps). The update is
        therefore monotonic in `observed_at`: a write carrying an
        OLDER `observed_at` than the stored row for this exact location
        is silently declined and leaves the stored row, including its
        `updated_at`, completely untouched. An equal `observed_at`
        still updates, so a genuine retry of the same observation that
        corrects the path still lands. A declined write affects zero
        rows in the Postgres adapter; that is correct, not a failure.
        """
        ...

    async def get(self, run_id: UUID, *, host: str | None, root: str | None) -> CapturePath | None:
        """Fetch the row for one exact (run_id, host, root); `None`
        when absent.

        Deliberately does NOT fall back to another location when the
        named one is missing: a locator naming the archive tier must
        never resolve to acquisition-tier bytes. Absence is the correct
        answer for a run never observed there, and for one whose row a
        future erasure slice removed.
        """
        ...

    async def get_latest(self, run_id: UUID) -> CapturePath | None:
        """Fetch the most recently OBSERVED row for a run_id, across
        every location; `None` when the run has none.

        Ordered by `observed_at` rather than preferring a tier, because
        the display consumer wants the copy most likely to still exist.
        Preferring the acquisition tier would point at exactly the copy
        that gets capacity-purged first.
        """
        ...


async def load_run_capture_path(store: CapturePathStore, run_id: UUID) -> str:
    """Resolve the observed path for a run_id; fallback when absent.

    Read-path convention mirroring `load_actor_display_name`: any
    handler surfacing this value calls this helper rather than
    inlining the `None` check. Returns `UNOBSERVED_CAPTURE_PATH` when
    no row exists, which the caller should treat as "not yet observed
    or rejected by the dual-clock guard," never as an error.

    A Run may now hold one row per storage location, so this returns
    the most recently observed of them. That is a DISPLAY convenience
    and deliberately lossy: it answers "where was this last seen",
    not "every place CORA has seen it". Once a slice observes the same
    file on a second tier, a reader wanting the full set should ask
    for it explicitly rather than widening this helper's meaning
    underneath its existing caller.
    """
    row = await store.get_latest(run_id)
    return row.observed_path if row else UNOBSERVED_CAPTURE_PATH


_UPSERT_SQL = """
INSERT INTO run_capture_path
    (run_id, observed_path, observed_at, created_at, updated_at, host, root)
VALUES ($1, $2, $3, $4, $4, $5, $6)
ON CONFLICT (run_id, host, root) DO UPDATE
    SET observed_path = EXCLUDED.observed_path,
        observed_at = EXCLUDED.observed_at,
        updated_at = now()
    WHERE EXCLUDED.observed_at >= run_capture_path.observed_at
"""

_GET_SQL = """
SELECT capture_path_id, run_id, observed_path, observed_at, created_at, updated_at, host, root
FROM run_capture_path
WHERE run_id = $1
  -- IS NOT DISTINCT FROM, not `=`: a legacy row carries NULL host and
  -- root, and `= NULL` is never true. The leading `run_id =` still
  -- drives an index cond; only these two degrade to a filter, over the
  -- handful of rows one run has. Do not "optimize" this to `=`.
  AND host IS NOT DISTINCT FROM $2
  AND root IS NOT DISTINCT FROM $3
"""

_LATEST_SQL = """
SELECT capture_path_id, run_id, observed_path, observed_at, created_at, updated_at, host, root
FROM run_capture_path
WHERE run_id = $1
ORDER BY observed_at DESC, updated_at DESC, capture_path_id DESC
LIMIT 1
"""


def _row_to_capture_path(row: asyncpg.Record) -> CapturePath:
    return CapturePath(
        capture_path_id=row["capture_path_id"],
        run_id=row["run_id"],
        observed_path=row["observed_path"],
        observed_at=row["observed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        host=row["host"],
        root=row["root"],
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
        host: str | None,
        root: str | None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                _UPSERT_SQL, run_id, observed_path, observed_at, created_at, host, root
            )

    async def get(self, run_id: UUID, *, host: str | None, root: str | None) -> CapturePath | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_GET_SQL, run_id, host, root)
        return _row_to_capture_path(row) if row is not None else None

    async def get_latest(self, run_id: UUID) -> CapturePath | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LATEST_SQL, run_id)
        return _row_to_capture_path(row) if row is not None else None


class InMemoryCapturePathStore:
    """Test / `app_env=test` adapter for `CapturePathStore`.

    Postgres semantics preserved, mirroring `InMemoryProfileStore`:
    on insert, `updated_at = created_at` (the caller's clock read); on
    update, `updated_at = datetime.now(tz=UTC)` (the DB's own clock at
    `ON CONFLICT DO UPDATE` time in the real adapter's `_UPSERT_SQL`,
    never the caller-supplied `created_at`, which the real adapter
    never even sends on the UPDATE branch).

    Also mirrors the real adapter's monotonic `WHERE` guard: an
    incoming `observed_at` older than the stored row's leaves that row
    completely untouched, `updated_at` included, so a declined write
    is invisible in both adapters.
    """

    def __init__(self) -> None:
        self._rows: dict[tuple[UUID, str | None, str | None], CapturePath] = {}

    async def upsert(
        self,
        *,
        run_id: UUID,
        observed_path: str,
        observed_at: datetime,
        created_at: datetime,
        host: str | None,
        root: str | None,
    ) -> None:
        key = (run_id, host, root)
        existing = self._rows.get(key)
        if existing is None:
            self._rows[key] = CapturePath(
                capture_path_id=uuid4(),
                run_id=run_id,
                observed_path=observed_path,
                observed_at=observed_at,
                created_at=created_at,
                updated_at=created_at,
                host=host,
                root=root,
            )
        elif observed_at >= existing.observed_at:
            self._rows[key] = CapturePath(
                # Preserved, mirroring the real ON CONFLICT DO UPDATE,
                # which never touches the surrogate key.
                capture_path_id=existing.capture_path_id,
                run_id=run_id,
                observed_path=observed_path,
                observed_at=observed_at,
                created_at=existing.created_at,
                updated_at=datetime.now(tz=UTC),
                host=host,
                root=root,
            )

    async def get(self, run_id: UUID, *, host: str | None, root: str | None) -> CapturePath | None:
        return self._rows.get((run_id, host, root))

    async def get_latest(self, run_id: UUID) -> CapturePath | None:
        """Mirrors `_LATEST_SQL` exactly, including its final
        `capture_path_id DESC` tiebreak. That third key is what makes
        the two adapters agree on a full `(observed_at, updated_at)`
        tie: without it this returns the first-inserted row while
        Postgres returns whatever its sort produced, and no test could
        pin the difference."""
        candidates = [row for (rid, _, _), row in self._rows.items() if rid == run_id]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda r: (r.observed_at, r.updated_at, r.capture_path_id),
        )


__all__ = [
    "UNOBSERVED_CAPTURE_PATH",
    "CapturePath",
    "CapturePathStore",
    "InMemoryCapturePathStore",
    "PostgresCapturePathStore",
    "load_run_capture_path",
]
