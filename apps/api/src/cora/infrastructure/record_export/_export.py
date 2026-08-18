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

Deliberately does not: write bundle files (that is Step 3/4's job, once
hashing and the manifest exist), or touch `entries_enclosure_permit_probes`
(S5c, still deferred: it holds every live entries row on the pilot
database and owes its own disclosure review; see
`project_record_completeness_design.md`).

`entries_run_feed_heartbeats` (S5a) and `entries_run_capture_probes`
(S5b) have no envelope either, so neither can be reached from the
envelope-driven walk below. Their rows are pulled separately, once, by a
whole-table unscoped read each after the walk finishes, via
`_registry.EntriesTableSpec.unscoped_reader`. That read shares this
function's caller's `REPEATABLE READ` snapshot (opened in `_shell.py`,
never here), same as every envelope-driven entries read above it, but
the entries tier as a whole remains snapshot-bounded while the streams
tier is xmin-bounded: an unscoped row can have been written by a
transaction that committed above the watermark. Not closable without a
`transaction_id` column on the entries tables; stated, not fixed, here.
"""

from dataclasses import dataclass
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
    """

    streams: tuple[dict[str, object], ...]
    logbooks: dict[str, tuple[dict[str, object], ...]]
    watermark: int = 0


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
    `capture_probe` since S5b) with one whole-table read each, keyed onto
    `logbooks` the same as an envelope-driven kind. Done once, after the
    walk, so a kind can never be read twice even if a future spec somehow
    declared both a `envelope_class` and an `unscoped_reader`.

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

    for row in rows:
        ensure_stream_type_known(row["stream_type"])
        streams.append(render_row(row))

        if row["event_type"] not in envelope_classes:
            continue
        payload = row["payload"]
        kind = payload["kind"]
        logbook_id = UUID(payload["logbook_id"])
        spec = resolve(kind)
        entries = await spec.reader(conn, logbook_id)
        logbooks.setdefault(kind, []).extend(render_row(entry) for entry in entries)

    for spec in all_specs():
        if spec.unscoped_reader is None:
            continue
        entries = await spec.unscoped_reader(conn)
        logbooks.setdefault(spec.kind, []).extend(render_row(entry) for entry in entries)

    return ExportedRecord(
        streams=tuple(streams),
        logbooks={kind: tuple(entries) for kind, entries in logbooks.items()},
        watermark=watermark,
    )
