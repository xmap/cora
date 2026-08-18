"""Walk the event store and follow every logbook envelope into its entries.

Per `project_record_export_v3.md` F0/F2: a single stream query over the
whole `events` table, ordered by `(transaction_id, position)`, bounded by
one `pg_snapshot_xmin(pg_current_snapshot())` watermark captured up front
(not re-evaluated per row, unlike the projection worker's catch-up query,
which this SQL otherwise mirrors) so the export sees one consistent
snapshot. On each row whose `event_type` names a `*LogbookOpened` class
(`registered_envelope_classes()`, from Step 1's `_registry`), `kind` and
`logbook_id` come straight out of the already-decoded `payload` dict and
resolve through Step 1's `resolve()` to the matching entries-tier reader.

Deliberately does not write bundle files: that is Step 3/4's job, once
hashing and the manifest exist.

`entries_run_feed_heartbeats` (S5a), `entries_run_capture_probes`
(S5b), and `entries_enclosure_permit_probes` (S5c) have no envelope, so
none can be reached from the envelope-driven walk below. Their rows are
pulled separately, once, by a whole-table unscoped read each after the
walk finishes, via `_registry.EntriesTableSpec.unscoped_reader`. That
read shares this function's caller's `REPEATABLE READ` snapshot (opened
in `_shell.py`, never here), same as every envelope-driven entries read
above it, but the entries tier as a whole remains snapshot-bounded
while the streams tier is xmin-bounded: an unscoped row can have been
written by a transaction that committed above the watermark. Not
closable without a `transaction_id` column on the entries tables;
stated, not fixed, here.

Also times each per-kind read (`ExportedRecord.read_seconds_by_logbook_kind`,
S5d), because this is the one place with a seam onto each individual
`spec.reader` / `spec.unscoped_reader` call; a caller outside this
module has no way to time a kind's read without re-issuing it a second
time against a different snapshot.

`capture_source_row_count_by_logbook_kind` (S2b) lives here too, alongside `capture_watermark`:
a second, independent count per registered kind (an unscoped `count(*)` on
each `spec.table`, sharing no predicate with any reader above) that
`_manifest.py` compares against what this walk actually put in
`ExportedRecord.logbooks`. See that function's own docstring for why
independence is not the same shape for the six envelope-driven kinds as it
is for the three unscoped ones.
"""

import time
from dataclasses import dataclass, field
from uuid import UUID

import asyncpg

from cora.infrastructure.record_export._registry import (
    all_specs,
    registered_envelope_classes,
    resolve,
)
from cora.infrastructure.record_export._render import render_row
from cora.infrastructure.record_export._stream_types import ensure_stream_type_known

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress at module level, matching the other
# entries-table readers.

_WATERMARK_SQL = "SELECT pg_snapshot_xmin(pg_current_snapshot())::text"

# Same column list as postgres_event_store.py's _LOAD_SQL and
# projection/worker.py's _ADVANCE_SQL. transaction_id is xid8; asyncpg has
# no output codec for it (same gap those two modules work around), so it
# is cast to text and aliased back onto its own name.
_STREAM_SQL = """
SELECT position, event_id, stream_type, stream_id, version, event_type,
       schema_version, payload, metadata, correlation_id, causation_id,
       principal_id, occurred_at, recorded_at,
       signature, signature_kid, signature_version,
       transaction_id::text AS transaction_id
FROM events
WHERE transaction_id < $1::xid8
ORDER BY transaction_id, position
"""


class EmptyExportError(RuntimeError):
    """Zero rows exported.

    Per the build brief's acceptance criteria: a bundle claiming to be
    the record with nothing in it is a bug in the caller (wrong
    database, unmigrated database, watermark set before anything was
    written), never a legitimate empty result to hand back quietly.
    """


@dataclass(frozen=True, slots=True)
class ExportedRecord:
    """One export's two tiers, rendered but not yet hashed or redacted.

    `streams` is every `events` row below the captured watermark, in
    `(transaction_id, position)` order. `logbooks` groups every
    entries-tier row pulled via an envelope by `kind`, in each kind's own
    registry order-by order; rows are UNFOLDED (one dict per row), never
    aggregated.

    `watermark` is the SAME xmin value `capture_watermark` produced and
    the stream query above was bounded by, carried on the record itself
    so `build_manifest` can read it here rather than take it as an
    independent parameter: a caller wanting "the watermark this export
    used" for the manifest had no way to obtain it other than by calling
    `capture_watermark` a SECOND time, which returns a different snapshot
    than the one the rows were actually bounded by. Defaults to 0 for
    hand-built test fixtures that do not exercise watermark plumbing;
    every real export sets it from the same call `export_record` used.

    `read_seconds_by_logbook_kind` is the wall-clock time spent inside
    `spec.reader` / `spec.unscoped_reader` calls for each kind, summed
    across every envelope occurrence for an envelope-driven kind (one
    call each time its `*LogbookOpened` envelope appears on the stream)
    or the one call for an unscoped kind. Times the read alone, not
    `render_row`. Added for S5d (`project_record_completeness_design.md`):
    the operator command needs a per-kind timing to make the first real
    export against a populated database a measurement rather than a
    fourth deferral argument. A kind absent from this dict was never
    read this export -- either it is `untraversed`, or it is an
    envelope-driven kind whose envelope never occurred, which the S4
    membership decision already treats as a genuine zero rather than a
    coverage gap. Defaults to an empty dict for the same hand-built-
    fixture reason `watermark` defaults to 0.
    """

    streams: tuple[dict[str, object], ...]
    logbooks: dict[str, tuple[dict[str, object], ...]]
    watermark: int = 0
    read_seconds_by_logbook_kind: dict[str, float] = field(default_factory=dict)


async def capture_source_row_count_by_logbook_kind(conn: asyncpg.Connection) -> dict[str, int]:
    """One independent count per registered kind, for S2b's `source_row_count`.

    Delegates to each spec's own `count_reader` (`_registry.py`'s
    `_make_count_reader`, `SELECT count(*) FROM <table>`, no predicate) so
    the SQL itself lives beside `reader` / `unscoped_reader` rather than
    being rebuilt here. Must run inside the SAME `REPEATABLE READ READ
    ONLY` transaction as `export_record`, so both counts and the traversal
    describe the same snapshot. Unlike `capture_watermark`, which
    `export_record` calls itself (its own docstring: "`export_record` is
    the sole caller"), this function has THREE callers today --
    `_shell.py`'s `export_bundle` and `record_bundle_export.py`'s
    `export_record_bundles` each call it directly, back to back with
    `export_record`, inside the transaction they both open; neither calls
    it FROM `export_record`. Deliberately not folded into `export_record`
    / carried on `ExportedRecord` the way `watermark` and
    `read_seconds_by_logbook_kind` are: doing so would make this dict a
    mandatory field on every hand-built `ExportedRecord` test fixture
    across this package (`_hashing.py`, `_redaction.py`, `_bundle.py`'s
    tests build dozens, none caring about row counts), and giving it a
    default would reopen exactly the "coverage field switched off by a
    default" hole this design exists to close for `build_manifest`'s own
    required `source_row_count_by_logbook_kind` parameter. The residual
    this leaves is real and stated rather than hidden: nothing
    structurally prevents a future caller from pairing this dict with an
    `ExportedRecord` from a DIFFERENT snapshot the way `write_bundle`'s
    `ManifestRecordMismatchError` prevents a mismatched record/manifest
    pair; today's two production callers avoid it by construction (one
    `conn`, one transaction, both calls before it closes), not by a type
    that makes the mistake impossible.

    Per `project_independent_check_principle.md`, this is the SECOND side of
    the check `_manifest.py`'s `_extent_by_logbook_kind` performs against
    `exported_row_count`. Independence is NOT uniform across the registry:

    - For the six envelope-scoped kinds, this query shares no predicate at
      all with `spec.reader` (which filters on `logbook_id`). A row whose
      envelope never reached the stream walk still shows up here, which is
      precisely the omission-at-origin signal this design exists to raise.
    - For the three unscoped kinds (`heartbeat`, `capture_probe`,
      `permit_probe`), `spec.unscoped_reader` already runs the identical
      `SELECT * FROM <table>` shape, in the same snapshot. This count cannot
      diverge from a correct fetch of that table: it is not independent in
      the "different rows" sense for these three. What it still catches is a
      row lost or duplicated between the fetch and `_manifest.py`'s render-
      stage tally (`exported_row_count = len(record.logbooks[kind])`), since
      this query never goes through `render_row` or the `logbooks` dict at
      all. State this plainly rather than implying uniform independence; see
      `tests/integration/test_record_export_row_count_independence_postgres.py`
      for the proof (and the live-DB negative result) on each side, and
      `test_manifest.py`'s render-stage-loss unit tests for the fetch-vs-
      render axis.

    Two limits worth stating in band rather than leaving implicit (the
    design memo's own "Adversaries, and what is actually caught" table
    names these as NOT CAUGHT by any form of this mechanism):

    - Rows deleted from a table before this count runs are invisible to
      BOTH sides alike; a divergence proves an omission, agreement never
      proves nothing was deleted upstream of the whole export.
    - A concurrent, unrelated long-lived transaction elsewhere in the
      database can pin `pg_snapshot_xmin` below the actual point this
      transaction's own snapshot was taken, so `_STREAM_SQL`'s explicit
      `transaction_id < watermark` filter can exclude an envelope whose
      committing transaction the REPEATABLE READ snapshot itself already
      considers visible -- the same streams-xmin-vs-entries-snapshot
      asymmetry `_export.py`'s own module docstring already names for the
      three unscoped kinds, but reachable here for an envelope-scoped kind
      too, because this count has no equivalent xmin bound (the entries
      tables carry no `transaction_id` column to bound it by). A divergence
      caused by this is real -- the rows genuinely are not in `logbooks` --
      but it is not evidence of a code defect in the traversal; a fresh
      retry captures a fresh watermark against a fresh snapshot and, absent
      an actual bug, will not reproduce it. A divergence that survives a
      retry is the actual signal to investigate. Closing this class fully
      needs the `transaction_id` column already named as unbuilt in the
      design memo's watch items; not done here.

    Valid ONLY because `export_record` is a whole-database export with no run
    or tenant filter (`_export.py`'s own module docstring): the same scoping
    caveat `_make_unscoped_reader` already carries for its own read.
    """
    counts: dict[str, int] = {}
    for spec in all_specs():
        counts[spec.kind] = await spec.count_reader(conn)
    return counts


async def capture_watermark(conn: asyncpg.Connection) -> int:
    """The xmin bound for one consistent export snapshot.

    Returns a plain `int`: asyncpg has no xid8 codec on either side, so
    (mirroring `projection/worker.py`'s bookmark parameter, the existing
    precedent for binding a value against an `xid8` column) the value is
    cast to `text` on the way out here and to `int` on the way back in,
    then bound as `$1::xid8` by the caller -- never compared as a string.

    `export_record` is the sole caller: it binds this value into the
    stream query AND carries it on the returned `ExportedRecord`, so
    there is exactly one snapshot per export and one place that reads it
    back.
    """
    value = await conn.fetchval(_WATERMARK_SQL)
    assert value is not None, "pg_snapshot_xmin(pg_current_snapshot()) returned NULL"
    return int(value)


async def export_record(conn: asyncpg.Connection) -> ExportedRecord:
    """Walk the whole event store and its envelope-linked logbooks.

    After the envelope-driven walk, also pulls every kind whose registry
    spec declares an `unscoped_reader` (`heartbeat` since S5a,
    `capture_probe` since S5b, `permit_probe` since S5c) with one
    whole-table read each, keyed onto `logbooks` the same as an
    envelope-driven kind. Done once, after the walk, so a kind can never
    be read twice even if a future spec somehow declared both a
    `envelope_class` and an `unscoped_reader`.

    Raises `EmptyExportError` on zero stream rows,
    `cora.infrastructure.record_export.UnknownStreamTypeError` on a
    `stream_type` outside the declared closed set (refuses immediately;
    never skips), and `UnknownLogbookKindError` on an envelope's `kind`
    with no registry entry.
    """
    watermark = await capture_watermark(conn)
    rows = await conn.fetch(_STREAM_SQL, watermark)
    if not rows:
        raise EmptyExportError(
            "export_record found zero events.rows below the captured "
            f"watermark ({watermark!r}); an empty record is never a "
            "valid export."
        )

    envelope_classes = registered_envelope_classes()
    streams: list[dict[str, object]] = []
    logbooks: dict[str, list[dict[str, object]]] = {}
    read_seconds: dict[str, float] = {}

    for row in rows:
        ensure_stream_type_known(row["stream_type"])
        streams.append(render_row(row))

        if row["event_type"] not in envelope_classes:
            continue
        payload = row["payload"]
        kind = payload["kind"]
        logbook_id = UUID(payload["logbook_id"])
        spec = resolve(kind)
        started = time.perf_counter()
        entries = await spec.reader(conn, logbook_id)
        read_seconds[kind] = read_seconds.get(kind, 0.0) + (time.perf_counter() - started)
        logbooks.setdefault(kind, []).extend(render_row(entry) for entry in entries)

    for spec in all_specs():
        if spec.unscoped_reader is None:
            continue
        started = time.perf_counter()
        entries = await spec.unscoped_reader(conn)
        read_seconds[spec.kind] = read_seconds.get(spec.kind, 0.0) + (time.perf_counter() - started)
        logbooks.setdefault(spec.kind, []).extend(render_row(entry) for entry in entries)

    return ExportedRecord(
        streams=tuple(streams),
        logbooks={kind: tuple(entries) for kind, entries in logbooks.items()},
        watermark=watermark,
        read_seconds_by_logbook_kind=read_seconds,
    )
