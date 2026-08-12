"""The export manifest: git commit, watermark, both profile hashes, and
the per-kind / per-event-type / per-run facts a reader needs before
trusting the bundle.

Per `project_record_export_build_brief.md` step 4 and
`project_record_export_v3.md` F8. All THREE of F5's hashes are namable
here now: `record_hash` (H1, the whole unredacted bundle, step 3),
`redaction_profile_hash` (H2, every table that decides what a published
record discloses, widened to both tiers by step 7's security review),
and `published_record_hash` (H3, the redacted projection's own hash,
added with the bundle writer). H3 is optional because an unredacted
bundle genuinely has none; see the field's own docstring for why its
absence is a signal rather than a default.

`build_manifest` is pure: every input it needs (`git_commit`,
`watermark`) is captured by the caller first and passed in, so the
function itself does no I/O and is trivial to test with synthetic
`ExportedRecord`s.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from cora.infrastructure.record_export._export import ExportedRecord
from cora.infrastructure.record_export._hashing import (
    TwoTierRecord,
    hash_record,
    hash_redacted_record,
    hash_redaction_profile,
)


@dataclass(frozen=True, slots=True)
class Manifest:
    """One export's provenance and shape, independent of its bytes on disk.

    `row_count_by_logbook_kind` and `max_schema_version_by_event_type`
    are reader-facing sanity checks: a reader can recompute both from
    the bundle itself and compare, catching truncation or a stale
    generator without needing to trust this manifest blindly.
    """

    git_commit: str
    watermark: int
    record_hash: str
    redaction_profile_hash: str
    row_count_by_logbook_kind: dict[str, int]
    max_schema_version_by_event_type: dict[str, int]
    is_simulated: bool
    expansion_digest_presence_by_run: dict[str, bool]
    published_record_hash: str | None = None
    """H3, present only on a manifest built alongside a redacted record.

    `None` means "this manifest describes an unredacted bundle", NOT
    "redaction produced nothing". A reader seeing `None` beside a bundle
    someone called published should treat the bundle as unverified: the
    absence is the signal.

    Safe to carry inside the bundle despite H3 covering that bundle,
    because H3 hashes the two tiers only. The manifest is not in its own
    hashed body, so there is no circularity to resolve.
    """


def capture_git_commit(*, cwd: Path | str | None = None) -> str:
    """The exporting checkout's HEAD commit SHA.

    No caching, no fallback: a failure here (detached submodule, no
    `.git`, corrupt repo) should stop the export rather than write a
    manifest that lies about provenance.
    """
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _require_str(value: object) -> str:
    assert isinstance(value, str)
    return value


def _payload(row: dict[str, object]) -> dict[str, object]:
    payload = row["payload"]
    assert isinstance(payload, dict)
    return cast("dict[str, object]", payload)


def _row_count_by_logbook_kind(record: ExportedRecord) -> dict[str, int]:
    return {kind: len(rows) for kind, rows in record.logbooks.items()}


def _max_schema_version_by_event_type(record: ExportedRecord) -> dict[str, int]:
    versions: dict[str, int] = {}
    for row in record.streams:
        event_type = row["event_type"]
        schema_version = row["schema_version"]
        assert isinstance(event_type, str)
        assert isinstance(schema_version, int)
        if schema_version > versions.get(event_type, 0):
            versions[event_type] = schema_version
    return versions


def _is_simulated(record: ExportedRecord) -> bool:
    """True unless an observation row explicitly says otherwise.

    Vacuously True when the export carries no observation rows at all:
    nothing in the bundle contradicts "this is a simulated record". A
    mixed result (some True, some False) reports as False rather than
    raising -- the manifest's job is to report the fact, not gate on it.
    """
    observations = record.logbooks.get("observation", ())
    return all(row["is_simulated"] is True for row in observations)


def _expansion_digest_presence_by_run(record: ExportedRecord) -> dict[str, bool]:
    """Per F8: a run has a pinned expansion digest iff at least one of its
    child Procedures was registered via `register_procedure_from_recipe`
    (carries a `RecipeExpansionRecorded` on its own stream). A Procedure
    registered directly, or a run recorded by observing an external
    scan, has no digest to compare against; that is correct, not a gap.
    """
    run_ids = {
        _require_str(row["stream_id"]) for row in record.streams if row["stream_type"] == "Run"
    }

    parent_run_by_procedure: dict[str, str | None] = {}
    expanded_procedures: set[str] = set()
    for row in record.streams:
        if row["event_type"] == "ProcedureRegistered":
            payload = _payload(row)
            parent_run_id = payload["parent_run_id"]
            parent_run_by_procedure[_require_str(payload["procedure_id"])] = (
                None if parent_run_id is None else _require_str(parent_run_id)
            )
        elif row["event_type"] == "RecipeExpansionRecorded":
            expanded_procedures.add(_require_str(_payload(row)["procedure_id"]))
    return {
        run_id: any(
            parent_run_id == run_id and procedure_id in expanded_procedures
            for procedure_id, parent_run_id in parent_run_by_procedure.items()
        )
        for run_id in run_ids
    }


def build_manifest(
    record: ExportedRecord,
    *,
    watermark: int,
    git_commit: str,
    redacted: TwoTierRecord | None = None,
) -> Manifest:
    """Assemble the manifest for one already-exported, already-rendered record.

    Pass `redacted` (a `RedactionResult.redacted_record`) when the bundle
    being written is the published projection, so the manifest carries
    H3. The shape counts stay derived from the UNREDACTED `record`:
    redaction never adds or removes a row, only rewrites values within
    one, so the counts describe both, and deriving them from the
    unredacted side keeps a reader's recomputation honest if redaction
    ever does start dropping rows.
    """
    return Manifest(
        git_commit=git_commit,
        watermark=watermark,
        record_hash=hash_record(record),
        redaction_profile_hash=hash_redaction_profile(),
        row_count_by_logbook_kind=_row_count_by_logbook_kind(record),
        max_schema_version_by_event_type=_max_schema_version_by_event_type(record),
        is_simulated=_is_simulated(record),
        expansion_digest_presence_by_run=_expansion_digest_presence_by_run(record),
        published_record_hash=None if redacted is None else hash_redacted_record(redacted),
    )


__all__ = ["Manifest", "build_manifest", "capture_git_commit"]
