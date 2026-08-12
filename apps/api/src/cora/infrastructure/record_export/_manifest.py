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

`build_manifest` is pure: every input it needs (`git_commit`; the
watermark comes off `record` itself) is captured by the caller first and
passed in, so the function itself does no I/O and is trivial to test
with synthetic `ExportedRecord`s.
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
from cora.infrastructure.record_export._redaction import RedactionResult
from cora.infrastructure.record_export._tokens import TokenMap


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
    unfired_tier2_clearances: tuple[str, ...] | None = None
    """Declared tier-2 jsonb clearances (`"kind/column/pointer"`) that
    never matched a row in a kind this export carried. `None` means "no
    redaction happened", the same absence-is-the-signal convention as
    `published_record_hash`; an empty tuple means redaction happened and
    every clearance fired.

    This is a COMPLETENESS fact, not a safety finding. Tier 2's
    dispositions are an allowlist, so an unfired clearance means a field
    was published less often than the profile permits, never more --
    see `unfired_clearances`'s own docstring for the full argument and
    the denylist-shaped mistake this field replaces (an earlier version
    aborted the export instead of reporting this). A reviewer reading a
    non-empty list here learns "this export was too narrow to exercise
    every rule the profile declares", which is a caveat about coverage,
    not a leak.
    """
    unfired_tier1_fields: tuple[str, ...] | None = None
    """The same completeness fact as `unfired_tier2_clearances`, one tier
    up: `"event_type/field"` pairs declared in the generated disposition
    table for an event type this export carried, whose field never
    appeared on any row of that type. Same `None`/empty-tuple convention.

    Almost always empty in practice: tier 1's table is exhaustively
    generated, and a declared field is normally present (even as `null`)
    on every row of an event type the current dataclass produces. A
    field appearing here means EVERY row of that event type in this
    export predates the `schema_version` that added the field -- one
    surviving row with the key present would have marked it fired -- a
    narrowness caveat about THIS export, not a leak; see
    `RedactionResult.unfired_tier1_fields`'s docstring for why a
    build-time guard cannot see this and a per-export field can.
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
    """False unless an observation row explicitly says otherwise.

    Matches the Run BC's own fold of this exact column
    (`postgres_run_channel_lookup.py`'s `coalesce(bool_or(is_simulated), false)`):
    an observation asserts simulated by being present and True, so the
    identity element for "no observations at all" is False, the same as
    `bool_or` over an empty set. The manifest previously used `all(...)`,
    whose empty-set identity is True, so a record with zero observation
    rows -- including the pilot's first genuine beamline-attached export,
    which had none -- was reported as simulated. A published record
    cannot carry that flag by an accident of aggregation identity.

    A mixed result (some True, some False) reports as True: ANY row
    asserting simulated is enough to call the whole export simulated,
    mirroring `bool_or`'s semantics exactly rather than requiring
    unanimity in either direction.
    """
    observations = record.logbooks.get("observation", ())
    return any(row["is_simulated"] is True for row in observations)


def _expansion_digest_presence_by_run(
    record: ExportedRecord, *, token_map: TokenMap | None = None
) -> dict[str, bool]:
    """Per F8: a run has a pinned expansion digest iff at least one of its
    child Procedures was registered via `register_procedure_from_recipe`
    (carries a `RecipeExpansionRecorded` on its own stream). A Procedure
    registered directly, or a run recorded by observing an external
    scan, has no digest to compare against; that is correct, not a gap.

    Without `token_map`, this dict is keyed by the RAW `stream_id` values
    pulled straight from the unredacted `record` -- harmless on a full
    bundle, but on a published one it would republish in plaintext
    exactly the Run identifiers tier-1 redaction already replaced with
    per-export surrogates in the streams body. Pass the SAME
    `RedactionResult.token_map` tier-1 redaction used (via `token_uuid`,
    memoized by source) so a run's key here always equals the surrogate
    a reader finds on that run's rows.
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
    by_raw_run_id = {
        run_id: any(
            parent_run_id == run_id and procedure_id in expanded_procedures
            for procedure_id, parent_run_id in parent_run_by_procedure.items()
        )
        for run_id in run_ids
    }
    if token_map is None:
        return by_raw_run_id
    return {
        _require_str(token_map.token_uuid(run_id)): value for run_id, value in by_raw_run_id.items()
    }


def _render_unfired_clearances(unfired: frozenset[tuple[str, str, str]]) -> tuple[str, ...]:
    return tuple(sorted(f"{kind}/{column}/{pointer}" for kind, column, pointer in unfired))


def _render_unfired_tier1_fields(unfired: frozenset[tuple[str, str]]) -> tuple[str, ...]:
    return tuple(sorted(f"{event_type}/{field}" for event_type, field in unfired))


def build_manifest(
    record: ExportedRecord,
    *,
    git_commit: str,
    redaction: RedactionResult | None = None,
) -> Manifest:
    """Assemble the manifest for one already-exported, already-rendered record.

    `watermark` is read from `record.watermark`, the value `export_record`
    itself captured and bounded its query by, rather than taken as a
    separate parameter: no caller could otherwise produce "the SAME value
    the query used" without calling `capture_watermark` a second time,
    which returns a different snapshot.

    Pass `redaction` (the `RedactionResult` `redact_record` returned) when
    the bundle being written is the published projection, so the manifest
    carries H3 and its per-run map is keyed by the same surrogates tier-1
    redaction already put on the streams body. The shape counts stay
    derived from the UNREDACTED `record` regardless: redaction never adds
    or removes a row, only rewrites values within one, so the counts
    describe both, and deriving them from the unredacted side keeps a
    reader's recomputation honest if redaction ever does start dropping
    rows.

    `redaction` carries `redacted_record`, `token_map`,
    `unfired_tier2_clearances` and `unfired_tier1_fields` together as one
    object, deliberately, not as four independently-omittable parameters:
    a caller could otherwise supply a `token_map` from an unrelated
    redaction (or none at all) alongside a genuinely redacted record,
    producing a manifest whose per-run keys disagree with the surrogates
    actually on the streams body; or supply `redacted` while omitting one
    of the completeness fields, silently reporting a false "everything
    fired" instead of the true count. All become structurally impossible
    once every one of them comes from the one `RedactionResult` a real
    redaction pass produced.
    """
    if redaction is None:
        redacted: TwoTierRecord | None = None
        token_map: TokenMap | None = None
        unfired_tier2: frozenset[tuple[str, str, str]] = frozenset()
        unfired_tier1: frozenset[tuple[str, str]] = frozenset()
    else:
        redacted = redaction.redacted_record
        token_map = redaction.token_map
        unfired_tier2 = redaction.unfired_tier2_clearances
        unfired_tier1 = redaction.unfired_tier1_fields
    return Manifest(
        git_commit=git_commit,
        watermark=record.watermark,
        record_hash=hash_record(record),
        redaction_profile_hash=hash_redaction_profile(),
        row_count_by_logbook_kind=_row_count_by_logbook_kind(record),
        max_schema_version_by_event_type=_max_schema_version_by_event_type(record),
        is_simulated=_is_simulated(record),
        expansion_digest_presence_by_run=_expansion_digest_presence_by_run(
            record, token_map=token_map
        ),
        published_record_hash=None if redacted is None else hash_redacted_record(redacted),
        unfired_tier2_clearances=(
            None if redacted is None else _render_unfired_clearances(unfired_tier2)
        ),
        unfired_tier1_fields=(
            None if redacted is None else _render_unfired_tier1_fields(unfired_tier1)
        ),
    )


__all__ = ["Manifest", "build_manifest", "capture_git_commit"]
