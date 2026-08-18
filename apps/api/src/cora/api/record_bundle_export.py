"""The record exporter's operator command (S5d).

`python -m cora.api.record_bundle_export DESTINATION` produces, from ONE
database snapshot, both bundles a record export can be: the full,
unredacted bundle under `DESTINATION/full/`, and the published,
redacted projection under `DESTINATION/published/`. It replaces the
ad-hoc script that produced the only bundle pair ever built from a live
database (still on the pilot host at
`/home/beams0/2BMB/dgursoy/cora-postdeploy-verify/{full,published}`),
whose two-bundle shape this command keeps but whose hand-wiring and
lack of a shared snapshot it does not.

## Why both, always

`_shell.export_bundle` produces only the full, unredacted bundle: it
calls `build_manifest(record, git_commit=...)` with no `redaction`, so
H3 (`published_record_hash`) is `None` and nothing is tokenized or
dropped. A command that could produce only that bundle, under a name an
operator reads as "make the record," is a disclosure hazard: nothing
about running it would tell a future operator that what they hold is
not publishable. This command removes the failure mode structurally
rather than flagging it after the fact -- there is no flag that selects
"just the full bundle," so there is nothing to default to accidentally.
Both bundles land at fixed, distinctly named paths every run.

## Why one snapshot

`full/` and `published/` are the same underlying rows under two
projections (H1 over the raw record, H3 over the redacted one). If they
came from two different `export_record` calls, "the published bundle is
a redaction of the full bundle" would not be true of the pair on disk,
and H1-versus-H3 comparison would stop meaning anything. This command
therefore calls `export_record` exactly once, inside one `REPEATABLE
READ READ ONLY` transaction, and builds both manifests and both bundles
from that single in-memory `ExportedRecord` after the transaction
closes -- the same reason `_shell.export_bundle`'s transaction cannot
live inside `export_record` itself: `capture_git_commit` shells out to
git and `write_bundle` does blocking multi-file disk I/O, and holding a
`REPEATABLE READ` snapshot open across either pins the database's xmin
horizon and blocks autovacuum cluster-wide for as long as they take.

## Refusals, not tracebacks

Three conditions are operator mistakes, not bugs, and are reported as a
clean refusal with no bundle written and no traceback:

  - `BundleDestinationNotEmptyError`: `DESTINATION/full/` or
    `DESTINATION/published/` already holds something. Checked for BOTH
    slots before the database is touched at all, so a mistake on one
    slot is caught before the other slot's write, or the export itself,
    ever starts.
  - `EmptyExportError`: the database has zero events below the captured
    watermark.
  - `RedactionProfileMismatchError`: this checkout's disposition table
    does not hash to what `redact_record` was told to expect. Reachable
    only if a future caller stops self-supplying `hash_redaction_profile()`
    as its own expectation (see `export_record_bundles`'s body); handled
    here defensively regardless, per
    `project_record_completeness_design.md`'s S5d traps.

All three are checked before EITHER `write_bundle` call runs (the two
destination checks before the pool even opens; `EmptyExportError` and
`RedactionProfileMismatchError` both fire while only manifests, not
bundles, exist), so "no bundle written" holds for all three without
needing the two writes themselves to be atomic as a pair.

Any other exception (a database connectivity failure, a coding defect)
is not caught here and surfaces as a traceback: only operator-shaped
conditions are softened. `LogbookKindRowCountMismatchError` (S2b, raised
from inside `build_manifest`) is deliberately NOT a fourth refusal: an
`included` kind's independent row count disagreeing with what the
traversal actually exported is not an operator mistake like the three
conditions above, so it is not softened into a "refused" line the same
way. It still fires before either `write_bundle` call (both manifests
are built up front), so "no bundle written" holds for it too. Unlike the
three refusals, though, this is not always evidence of a code defect:
`capture_source_row_count_by_logbook_kind`'s own docstring names a
benign, concurrency-driven cause specific to envelope-scoped kinds (a
straggling transaction elsewhere pinning the stream walk's xmin
watermark below this export's own snapshot), which a plain retry -- a fresh
watermark against a fresh snapshot -- will usually not reproduce. A
divergence that reproduces across a retry is the one worth escalating as
a real omission; treat one occurrence as "retry once, then look closer,"
not as an incident on its own. Residual worth naming: if `write_bundle` ever
raised `ManifestRecordMismatchError` on the SECOND call (`published/`),
after the first call (`full/`) already succeeded, this function would
propagate that traceback with `full/` already complete on disk and
`published/` absent. Today that pairing cannot actually disagree --
`full_manifest` and `published_manifest` are both built from the same
`record` in the same call, immediately before each write -- so this is
a structural guarantee, not a runtime check, and it would take a future
edit that decouples manifest-building from record-being-written to
reopen it. A crash with a visible traceback is not the disclosure
hazard this command exists to close either way: nothing about a lone,
plainly-named `full/` directory and a stack trace reads as "here is
your publishable bundle."

## The report is a measurement, not a fourth argument

Three consecutive slices (S5a, S5b, S5c) argued that a single-round-trip
unscoped read was acceptable without ever running one against a
populated database. The report this command prints states, per
registered logbook kind, its `extent` status, its exported row count, its
independent source row count (S2b's `source_row_count`; the two can only
ever agree by the time either reaches this report, since `build_manifest`
raises before printing anything if they don't), and the wall-clock time
`export_record` spent reading it (`ExportedRecord.read_seconds_by_logbook_kind`,
added in `_export.py` for S5d: it is the only place with a seam onto each
individual `spec.reader` / `spec.unscoped_reader` call), plus each
bundle's total byte count and the command's total elapsed time. Counts
and timings only: no row contents are printed.

## Exit codes

  - `0`: both bundles written.
  - `2`: refused. One of the three conditions above; the message printed
    names which.

Nothing else is defined; an uncaught exception exits via Python's own
non-zero status, not one of these two.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cora.infrastructure.config import Settings
from cora.infrastructure.postgres.pool import create_pool
from cora.infrastructure.record_export import (
    BundleDestinationNotEmptyError,
    EmptyExportError,
    LogbookKindExtentStatus,
    RedactionProfileMismatchError,
    build_manifest,
    capture_git_commit,
    capture_source_row_count_by_logbook_kind,
    export_record,
    hash_redaction_profile,
    redact_record,
    write_bundle,
)

if TYPE_CHECKING:
    import asyncpg

    from cora.infrastructure.record_export import ExportedRecord, Manifest

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose on Pool.acquire/Connection.transaction; suppress
# at module level, matching _shell.py and _export.py.

FULL_DIRNAME = "full"
PUBLISHED_DIRNAME = "published"

_EXIT_CLEAN = 0
_EXIT_REFUSED = 2

_REFUSAL_ERRORS = (BundleDestinationNotEmptyError, EmptyExportError, RedactionProfileMismatchError)


@dataclass(frozen=True, slots=True)
class _KindLine:
    """One `extent_by_logbook_kind` row of the printed report."""

    kind: str
    status: str
    exported_row_count: int
    source_row_count: int | None
    """The independent unscoped `count(*)` (S2b), or `None` for a kind
    whose status left it absent from `source_row_count_by_logbook_kind` -- see
    `LogbookKindExtent.source_row_count`. An `included` kind reaching this
    report already agrees with `exported_row_count`: `build_manifest`
    raises `LogbookKindRowCountMismatchError` before either bundle is written
    if the two disagree, so a divergence never reaches a printed report."""
    read_seconds: float | None
    """`None` for a kind never read this export (`untraversed`, or an
    `included` envelope-driven kind whose envelope never occurred, which
    is a genuine zero read rather than an unknown one -- see
    `_kind_lines`). Otherwise the summed wall-clock time
    `export_record` spent reading it."""

    def render(self) -> str:
        read = "n/a" if self.read_seconds is None else f"{self.read_seconds:.3f}s"
        source = "n/a" if self.source_row_count is None else str(self.source_row_count)
        return (
            f"  {self.kind:<15} status={self.status:<11} "
            f"rows={self.exported_row_count:<8} source={source:<8} read={read}"
        )


@dataclass(frozen=True, slots=True)
class _Report:
    git_commit: str
    watermark: int
    kinds: tuple[_KindLine, ...]
    full_destination: Path
    published_destination: Path
    full_bundle_bytes: int
    published_bundle_bytes: int
    elapsed_seconds: float

    def render(self) -> str:
        lines = [
            "record bundle export",
            f"  git_commit={self.git_commit} watermark={self.watermark}",
            *(line.render() for line in self.kinds),
            f"  full bundle:      {self.full_destination}  ({self.full_bundle_bytes} bytes)",
            f"  published bundle: {self.published_destination}  "
            f"({self.published_bundle_bytes} bytes)",
            f"  elapsed: {self.elapsed_seconds:.3f}s",
        ]
        return "\n".join(lines)


def _refuse_if_occupied(destination: Path) -> None:
    """Mirrors `write_bundle`'s own non-empty-destination check, run for
    one bundle slot. Called for BOTH slots before either write, and
    before the database is touched, so an operator mistake on one slot
    never costs a real export attempt."""
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise BundleDestinationNotEmptyError(destination)


def _bundle_bytes(destination: Path) -> int:
    return sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())


def _kind_lines(record: ExportedRecord, manifest: Manifest) -> tuple[_KindLine, ...]:
    """`exported_row_count` and `source_row_count` come straight off the
    manifest's own `extent_by_logbook_kind` rather than being recomputed
    from `record` here: the manifest already carries both (S2b), and
    `record` is only still needed for `read_seconds_by_logbook_kind`, which
    has no manifest-side home."""
    lines: list[_KindLine] = []
    for kind in sorted(manifest.extent_by_logbook_kind):
        extent = manifest.extent_by_logbook_kind[kind]
        read_seconds = (
            record.read_seconds_by_logbook_kind.get(kind, 0.0)
            if extent.status == LogbookKindExtentStatus.INCLUDED
            else None
        )
        lines.append(
            _KindLine(
                kind=kind,
                status=extent.status.value,
                exported_row_count=extent.exported_row_count,
                source_row_count=extent.source_row_count,
                read_seconds=read_seconds,
            )
        )
    return tuple(lines)


async def export_record_bundles(*, destination: Path, database_url: str | None = None) -> int:
    """Run the command. `database_url` overrides the Settings value so
    the integration tier can point a run at its per-test database; the
    CLI always uses the deployment's own configuration.

    See the module docstring for the one-snapshot, both-bundles,
    refuse-cleanly design this function implements.
    """
    full_dir = destination / FULL_DIRNAME
    published_dir = destination / PUBLISHED_DIRNAME
    try:
        _refuse_if_occupied(full_dir)
        _refuse_if_occupied(published_dir)
    except _REFUSAL_ERRORS as exc:
        print(f"refused: {exc}")
        return _EXIT_REFUSED

    settings = Settings()
    pool = await create_pool(
        database_url if database_url is not None else settings.database_url,
        min_size=1,
        max_size=4,
    )
    started = time.perf_counter()
    try:
        try:
            async with pool.acquire() as conn:
                pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
                async with pg_conn.transaction(isolation="repeatable_read", readonly=True):
                    record = await export_record(pg_conn)
                    source_row_count_by_logbook_kind = (
                        await capture_source_row_count_by_logbook_kind(pg_conn)
                    )

            git_commit = capture_git_commit()
            full_manifest = build_manifest(
                record,
                git_commit=git_commit,
                source_row_count_by_logbook_kind=source_row_count_by_logbook_kind,
            )
            redaction = redact_record(
                record, expected_redaction_profile_hash=hash_redaction_profile()
            )
            published_manifest = build_manifest(
                record,
                git_commit=git_commit,
                source_row_count_by_logbook_kind=source_row_count_by_logbook_kind,
                redaction=redaction,
            )

            write_bundle(record, full_manifest, full_dir)
            write_bundle(redaction.redacted_record, published_manifest, published_dir)
        except _REFUSAL_ERRORS as exc:
            print(f"refused: {exc}")
            return _EXIT_REFUSED
    finally:
        await pool.close()

    report = _Report(
        git_commit=git_commit,
        watermark=record.watermark,
        kinds=_kind_lines(record, full_manifest),
        full_destination=full_dir,
        published_destination=published_dir,
        full_bundle_bytes=_bundle_bytes(full_dir),
        published_bundle_bytes=_bundle_bytes(published_dir),
        elapsed_seconds=time.perf_counter() - started,
    )
    print(report.render())
    return _EXIT_CLEAN


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface, separate from `main` so tests can pin the
    destination without touching a database."""
    parser = argparse.ArgumentParser(
        prog="python -m cora.api.record_bundle_export",
        description=(
            "Export CORA's record as two bundles from one database "
            f"snapshot: an unredacted bundle under DESTINATION/{FULL_DIRNAME}/ "
            f"and the published, redacted projection under "
            f"DESTINATION/{PUBLISHED_DIRNAME}/. Always writes both, so which "
            "one an operator has is never a guess. Refuses cleanly, writing "
            "nothing, if either subdirectory already holds anything, if "
            "the database has nothing to export, or if this checkout's "
            "redaction disposition table does not hash to what it expects."
        ),
    )
    parser.add_argument(
        "destination",
        type=Path,
        help=f"Directory to hold {FULL_DIRNAME}/ and {PUBLISHED_DIRNAME}/.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(export_record_bundles(destination=args.destination))


if __name__ == "__main__":
    sys.exit(main())
