"""export_bundle: the production entrypoint. Nothing outside this
package and its tests calls `export_record` or `write_bundle` today;
the one bundle ever produced from a live database was built by an
ad-hoc script wiring the same calls by hand, with no enclosing
transaction. This is the seam that replaces that script.

## Why the transaction lives here, not in `export_record`

`export_record`'s own module docstring promises "one consistent export
snapshot", but that promise only ever held for the `events` tier: its
stream query is bounded by a captured `xmin` watermark, while the
per-envelope entries reads (one per logbook kind, `_export.py`) carry
no watermark and no `transaction_id` column, by design. With no
enclosing transaction, each of those reads takes its own snapshot under
READ COMMITTED, so a write landing in the gap between two of them can
already tear the exported record today.

Wrapping `export_record`'s call in one `REPEATABLE READ READ ONLY`
transaction fixes the snapshot at the transaction's first statement
(`capture_watermark`'s own query) and holds it for every later read in
the same transaction, entries included. A count query added later to
check the entries tier independently has to share this exact snapshot
to mean anything, which is why the transaction has to live in the shell
that calls `export_record`, not inside it.

That transaction must also CLOSE before `build_manifest` and
`write_bundle` run. Neither touches `conn`: `capture_git_commit` spawns
a git subprocess and `write_bundle` does a blocking multi-file disk
write. Holding a REPEATABLE READ snapshot open across either pins the
database's xmin horizon and blocks autovacuum cluster-wide for as long
as they take, seconds to tens of seconds on the pilot host, which also
carries the live control path.

`export_bundle` must own the transaction it opens: handing it a
connection already inside a transaction at a different isolation level
makes asyncpg raise `InterfaceError` rather than silently degrading to
a nested savepoint.
"""

from pathlib import Path

import asyncpg

from cora.infrastructure.record_export._bundle import write_bundle
from cora.infrastructure.record_export._export import export_record
from cora.infrastructure.record_export._manifest import build_manifest, capture_git_commit

# pyright: reportUnknownMemberType=false
# asyncpg's stubs are loose on Connection.transaction; suppress at module
# level, matching _export.py and _registry.py.

__all__ = ["export_bundle"]


async def export_bundle(conn: asyncpg.Connection, destination: Path) -> Path:
    """Capture the watermark, export the record, build the manifest,
    write the bundle. `write_bundle` is the final step: it writes
    `destination`'s `manifest.json`, `streams.jsonl` and `logbooks/`,
    refusing if `destination` already holds anything.

    The watermark capture and the export happen inside one `REPEATABLE
    READ READ ONLY` transaction opened here, so the events stream and
    every per-kind entries read share one fixed snapshot; see the
    module docstring for why that transaction cannot live inside
    `export_record` itself, and why it closes before the manifest and
    bundle steps run.
    """
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        record = await export_record(conn)
    manifest = build_manifest(record, git_commit=capture_git_commit())
    return write_bundle(record, manifest, destination)
