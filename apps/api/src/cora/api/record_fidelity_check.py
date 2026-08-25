"""The D6 record-fidelity operator command.

`python -m cora.api.record_fidelity_check BUNDLE_ROOT` refolds every Run
in a record export bundle offline and verifies the folded state against
the same Run loaded live from Postgres. This is the assembly the JSR
paper's `notes/rehearsal-pinning.md` names as missing: "a tool that
exports a run's ledger slice, refolds it offline, computes the fidelity
hash, and verifies it against the record, exercised as a test." Every
component (the pure `fold`, `from_stored`, `compute_content_hash`, the
bundle reader) already existed; this wires them together and runs the
result against real exported data instead of scenario fixtures.

## What this proves, and what it does not

Both sides, the refold from the bundle and the live load from Postgres,
go through the SAME `cora.run.aggregates.run.fold`. That proves the
export is a faithful carrier of state: it catches a row dropped or
reordered in the export, jsonb round-trip drift, or damage from
redaction. It CANNOT catch a bug in the evolver itself, because a wrong
evolver folds identically wrong on both sides. This is the paper's own
"state versus record" seam, not "record versus world": it says nothing
about whether the record matches what happened at the beamline.

## Two bundle slots, two different questions

`full/` supports the real check: refold, then compare against the live
database by `stream_id`. `published/` cannot be identity-matched at
all -- `_redact_tier1.py`'s `TokenMap` replaces `stream_id` with a fresh
`uuid4()` per export and the mapping never ships, so a published run
cannot be looked up in the live database by any means. For `published/`
this command can only ask "does this refold without error", never "does
it match", and reports that limitation rather than hiding it behind a
misleadingly reassuring green line. A published run that fails to
refold is not necessarily a bug: tier-1 redaction drops or tokenizes
payload fields `from_stored` may require.

## Exit codes

  0 -- every `full/` run refolded and matched the live database.
  1 -- at least one `full/` run refolded but produced a state hash that
       disagrees with the live one. A genuine fidelity finding.
  2 -- operator problem: the bundle is not readable (missing
       `manifest.json` or `streams.jsonl`), or it carries no Run stream
       to check at all.

`published/` results are always reported, never gate the exit code:
its unrefolded count is expected-shaped evidence, not a command
failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast
from uuid import UUID

from cora.api.record_bundle_export import FULL_DIRNAME, PUBLISHED_DIRNAME
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.config import Settings
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.postgres.pool import create_pool
from cora.infrastructure.record_export import (
    MANIFEST_NAME,
    MalformedBundleError,
    read_bundle_body,
    render_value,
)
from cora.run.aggregates.run import Run, fold, from_stored, load_run
from cora.shared.content_hash import compute_content_hash

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

RUN_STATE_PAYLOAD_TYPE = "application/vnd.cora.run-state+json"

_EXIT_CLEAN = 0
_EXIT_MISMATCH = 1
_EXIT_REFUSED = 2

_NO_RUNS_MESSAGE = "carries no Run stream to verify"


@dataclass(frozen=True, slots=True)
class _RunResult:
    """One run's refold outcome. Exactly one of `state_hash_refolded` /
    `refold_error` is set; `state_hash_recorded` and `digests_match`
    stay `None` for a `published/` row, where no live comparison is
    possible at all."""

    run_id: str
    event_count: int
    fold_ms: float
    actuation_kind: str | None
    state_hash_recorded: str | None
    state_hash_refolded: str | None
    digests_match: bool | None
    refold_error: str | None

    def as_json(self) -> dict[str, object]:
        """Superset of the D2 rehearsal-pinning export contract
        (`papers/2026-jsr-cora/data/2bm_rehearsal.json`, consumed by
        `figures/render_f5.py` / `render_t2.py`): the `steps_hash_*` /
        `bindings_hash_*` keys that contract expects come from
        `ResolvedStepsRecorded` on a Procedure stream, which no
        witnessed run carries, so they are always `None` here. Kept in
        the shape rather than omitted so a future merge of this
        output into that data file is a key-union, not a schema
        migration."""
        return {
            "run_id": self.run_id,
            "event_count": self.event_count,
            "fold_ms": self.fold_ms,
            "actuation_kind": self.actuation_kind,
            "steps_hash_recorded": None,
            "steps_hash_refolded": None,
            "bindings_hash_recorded": None,
            "bindings_hash_refolded": None,
            "state_hash_recorded": self.state_hash_recorded,
            "state_hash_refolded": self.state_hash_refolded,
            "digests_match": self.digests_match,
            "worked_example": False,
            "refold_error": self.refold_error,
        }


@dataclass(frozen=True, slots=True)
class _BundleSummary:
    label: str
    runs: int
    refolded: int
    matched: int | None
    mismatched: int | None
    unrefolded: int
    note: str | None

    def render(self) -> str:
        line = f"  {self.label:<11} runs={self.runs:<6} refolded={self.refolded:<6}"
        if self.matched is not None and self.mismatched is not None:
            line += f" matched={self.matched:<6} mismatched={self.mismatched}"
        else:
            line += f" unrefolded={self.unrefolded}"
        if self.note is not None:
            line += f"  ({self.note})"
        return line


@dataclass(frozen=True, slots=True)
class _Report:
    bundle_root: Path
    git_commit: str
    full_bundle: _BundleSummary
    published_bundle: _BundleSummary
    elapsed_seconds: float

    def render(self) -> str:
        lines = [
            "record fidelity check",
            f"  bundle={self.bundle_root} git_commit={self.git_commit}",
            self.full_bundle.render(),
            self.published_bundle.render(),
            f"  elapsed: {self.elapsed_seconds:.3f}s",
        ]
        return "\n".join(lines)


def _parse_uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))


def _stored_event_from_row(row: Mapping[str, object]) -> StoredEvent:
    """Rebuild a `StoredEvent` envelope from one exported `streams.jsonl`
    row. `from_stored` (the fold seam) reads only `event_type` and
    `payload`, but the envelope is rebuilt in full anyway so this seam
    stays honest about what a bundle row actually carries, and so a
    later shape-view tool has a typed envelope to work from rather
    than a bag of JSON.

    Handles both bundle shapes. A published row has no `metadata` or
    `signature*` keys at all (tier-1 drops them, `_redact_tier1.py`
    `FIXED_DROP_COLUMNS`); `.get(...)` covers their absence.
    `transaction_id` is a string in the full bundle (asyncpg has no
    `xid8` codec) but a densified int in the published one (tier-1
    re-indexes it); `int(...)` normalizes both.
    """
    signature = row.get("signature")
    return StoredEvent(
        position=int(cast("int", row["position"])),
        event_id=UUID(str(row["event_id"])),
        stream_type=str(row["stream_type"]),
        stream_id=UUID(str(row["stream_id"])),
        version=int(cast("int", row["version"])),
        event_type=str(row["event_type"]),
        schema_version=int(cast("int", row["schema_version"])),
        payload=cast("dict[str, object]", row["payload"]),
        correlation_id=UUID(str(row["correlation_id"])),
        causation_id=_parse_uuid(row.get("causation_id")),
        occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
        recorded_at=datetime.fromisoformat(str(row["recorded_at"])),
        metadata=cast("dict[str, object]", row.get("metadata") or {}),
        transaction_id=int(cast("int", row["transaction_id"])),
        principal_id=_parse_uuid(row.get("principal_id")),
        signature=None if signature is None else bytes.fromhex(str(signature)),
        signature_kid=cast("str | None", row.get("signature_kid")),
        signature_version=cast("str | None", row.get("signature_version")),
    )


def _render_run_state(run: Run) -> dict[str, object]:
    """Render every folded `Run` field to JSON primitives, for content
    hashing. Reuses `record_export`'s own `render_value` (UUID -> str,
    datetime -> UTC ISO-8601) for scalar fields; frozensets and VO
    wrappers are unwrapped explicitly here, matching the sort-by-hand
    style `canonical_assembly_subset` established for the same kind of
    canonical-content rendering.

    Deliberately NOT `content_subset()`-shaped: that convention
    (`Method`, `Plan`, `Assembly`) excludes `id` / `status` / `version`
    because it hashes identity-relevant content for VERSIONING. A
    fidelity check needs the full folded state, `status` included, or
    a status-only divergence would hash identically on both sides and
    the check would miss exactly the class of bug it exists to catch.
    """
    return {
        "id": render_value(run.id),
        "name": run.name.value,
        "plan_id": render_value(run.plan_id),
        "subject_id": render_value(run.subject_id),
        "raid": run.raid,
        "status": run.status.value,
        "conduct_mode": run.conduct_mode.value,
        "override_parameters": run.override_parameters,
        "effective_parameters": run.effective_parameters,
        "trigger_source": run.trigger_source,
        "observation_logbook_id": render_value(run.observation_logbook_id),
        "external_refs": sorted(
            ({"scheme": ref.scheme, "value": ref.value} for ref in run.external_refs),
            key=lambda ref: (ref["scheme"], ref["value"]),
        ),
        "campaign_id": render_value(run.campaign_id),
        "last_adjusted_at": render_value(run.last_adjusted_at),
        "last_adjusted_by": render_value(run.last_adjusted_by),
        "adjustment_count": run.adjustment_count,
        "pinned_calibration_ids": sorted(str(x) for x in run.pinned_calibration_ids),
        "input_dataset_ids": sorted(str(x) for x in run.input_dataset_ids),
        "actuation_kind": run.actuation_kind,
        "hold_claims": [[str(claim_id), cause] for claim_id, cause in run.hold_claims],
    }


def _run_state_hash(run: Run | None) -> str | None:
    if run is None:
        return None
    return compute_content_hash(RUN_STATE_PAYLOAD_TYPE, _render_run_state(run))


def _row_slices_by_run_id(
    streams: Sequence[Mapping[str, object]],
) -> dict[str, list[Mapping[str, object]]]:
    """Group `streams.jsonl` rows into per-run slices, preserving each
    row's original file position within its run. The file order is
    `ORDER BY transaction_id, position` (`_export.py`) and is
    load-bearing for `fold`, so this is a single linear accumulation
    over the file's own order, never a sort."""
    slices: dict[str, list[Mapping[str, object]]] = {}
    for row in streams:
        if row.get("stream_type") != "Run":
            continue
        run_id = str(row["stream_id"])
        slices.setdefault(run_id, []).append(row)
    return slices


def _fold_run(rows: Sequence[Mapping[str, object]]) -> tuple[Run | None, float, str | None]:
    """Fold one run's row slice. Returns `(run, fold_ms, error)`; exactly
    one of `run` / `error` is set. Catches `ValueError` / `KeyError`
    narrowly: that is `from_stored`'s own documented failure mode for
    an unknown event type or a payload a tier-1 disposition has
    stripped a required field from, which is the expected
    `published/` failure this command exists to surface, not a defect
    to propagate as a traceback."""
    started = time.perf_counter()
    try:
        events = [from_stored(_stored_event_from_row(row)) for row in rows]
        run = fold(events)
    except (ValueError, KeyError) as exc:
        return None, (time.perf_counter() - started) * 1000, str(exc)
    fold_ms = (time.perf_counter() - started) * 1000
    if run is None:
        return None, fold_ms, "fold produced no state"
    return run, fold_ms, None


async def _check_full_run(
    run_id: str, rows: list[Mapping[str, object]], store: PostgresEventStore
) -> _RunResult:
    refolded, fold_ms, error = _fold_run(rows)
    refolded_hash = _run_state_hash(refolded)
    recorded = None if error is not None else await load_run(store, UUID(run_id))
    recorded_hash = _run_state_hash(recorded)
    both_present = refolded_hash is not None and recorded_hash is not None
    return _RunResult(
        run_id=run_id,
        event_count=len(rows),
        fold_ms=fold_ms,
        actuation_kind=None if refolded is None else refolded.actuation_kind,
        state_hash_recorded=recorded_hash,
        state_hash_refolded=refolded_hash,
        digests_match=(refolded_hash == recorded_hash) if both_present else None,
        refold_error=error,
    )


def _check_published_run(run_id: str, rows: list[Mapping[str, object]]) -> _RunResult:
    refolded, fold_ms, error = _fold_run(rows)
    refolded_hash = _run_state_hash(refolded)
    return _RunResult(
        run_id=run_id,
        event_count=len(rows),
        fold_ms=fold_ms,
        actuation_kind=None if refolded is None else refolded.actuation_kind,
        state_hash_recorded=None,
        state_hash_refolded=refolded_hash,
        digests_match=None,
        refold_error=error,
    )


def _full_summary(results: list[_RunResult]) -> _BundleSummary:
    refolded = sum(1 for r in results if r.refold_error is None)
    return _BundleSummary(
        label=f"{FULL_DIRNAME}/",
        runs=len(results),
        refolded=refolded,
        matched=sum(1 for r in results if r.digests_match is True),
        mismatched=sum(1 for r in results if r.digests_match is False),
        unrefolded=len(results) - refolded,
        note=None,
    )


def _published_summary(results: list[_RunResult]) -> _BundleSummary:
    refolded = sum(1 for r in results if r.refold_error is None)
    return _BundleSummary(
        label=f"{PUBLISHED_DIRNAME}/",
        runs=len(results),
        refolded=refolded,
        matched=None,
        mismatched=None,
        unrefolded=len(results) - refolded,
        note="identity tokenized, match not computable",
    )


def _read_manifest_git_commit(destination: Path) -> str:
    manifest = json.loads((destination / MANIFEST_NAME).read_text(encoding="utf-8"))
    return str(manifest["git_commit"])


async def check_record_fidelity(
    *,
    bundle_root: Path,
    database_url: str | None = None,
    json_out: Path | None = None,
) -> int:
    """Run the command. `database_url` overrides the Settings value so
    the integration tier can point a run at its per-test database; the
    CLI always uses the deployment's own configuration.

    See the module docstring for the two-slot, live-comparison-only-
    for-`full/`, non-gating-`published/` design this function
    implements.
    """
    full_dir = bundle_root / FULL_DIRNAME
    published_dir = bundle_root / PUBLISHED_DIRNAME
    try:
        full_body = read_bundle_body(full_dir)
        published_body = read_bundle_body(published_dir)
    except MalformedBundleError as exc:
        print(f"refused: {exc}")
        return _EXIT_REFUSED

    full_slices = _row_slices_by_run_id(cast("list[Mapping[str, object]]", full_body["streams"]))
    if not full_slices:
        print(f"refused: {full_dir} {_NO_RUNS_MESSAGE}")
        return _EXIT_REFUSED
    published_slices = _row_slices_by_run_id(
        cast("list[Mapping[str, object]]", published_body["streams"])
    )

    git_commit = _read_manifest_git_commit(full_dir)
    started = time.perf_counter()

    settings = Settings()
    pool = await create_pool(
        database_url if database_url is not None else settings.database_url,
        min_size=1,
        max_size=4,
    )
    try:
        store = PostgresEventStore(pool)
        full_results = [
            await _check_full_run(run_id, rows, store) for run_id, rows in full_slices.items()
        ]
    finally:
        await pool.close()

    published_results = [
        _check_published_run(run_id, rows) for run_id, rows in published_slices.items()
    ]

    full_summary = _full_summary(full_results)
    published_summary = _published_summary(published_results)
    report = _Report(
        bundle_root=bundle_root,
        git_commit=git_commit,
        full_bundle=full_summary,
        published_bundle=published_summary,
        elapsed_seconds=time.perf_counter() - started,
    )
    print(report.render())

    if json_out is not None:
        payload = {
            "bundle_root": str(bundle_root),
            "git_commit": git_commit,
            "full_bundle": {
                **asdict(full_summary),
                "rows": [r.as_json() for r in full_results],
            },
            "published_bundle": {
                **asdict(published_summary),
                "rows": [r.as_json() for r in published_results],
            },
        }
        await asyncio.to_thread(
            json_out.write_text,
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return _EXIT_MISMATCH if full_summary.mismatched else _EXIT_CLEAN


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface, separate from `main` so tests can pin the
    bundle path and `--json-out` without touching a database."""
    parser = argparse.ArgumentParser(
        prog="python -m cora.api.record_fidelity_check",
        description=(
            "Refold every Run in a record export bundle offline and verify "
            "the folded state against the same Run loaded live from "
            "Postgres, proving the export is a faithful carrier of state. "
            "Checks both bundle slots: the unredacted full/ bundle supports "
            "a live comparison; the published/ bundle's tokenized identity "
            "cannot be looked up at all, so it is only checked for whether "
            "it refolds. This cannot catch a bug in the evolver itself -- "
            "both sides fold through the same evolver -- only a fault in "
            "the export path between them."
        ),
    )
    parser.add_argument(
        "bundle_root",
        type=Path,
        help=(
            f"Directory holding {FULL_DIRNAME}/ and {PUBLISHED_DIRNAME}/, "
            "as written by record_bundle_export."
        ),
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write the per-run fidelity report as JSON to this path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(check_record_fidelity(bundle_root=args.bundle_root, json_out=args.json_out))


if __name__ == "__main__":
    sys.exit(main())
