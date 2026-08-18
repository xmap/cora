"""Unit tests for the export manifest.

`build_manifest` is pure (no I/O): every input is passed in, so these
tests construct synthetic `ExportedRecord`s directly rather than going
through a live database. The DB-backed acceptance path (via a real
Procedure + Run) lives in
`tests/integration/test_record_export_manifest_postgres.py`.
"""

import re
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.record_export import (
    MANIFEST_SCHEMA_VERSION,
    EntriesTableSpec,
    ExportedRecord,
    LogbookKindExtentStatus,
    LogbookKindRowCountMismatchError,
    Manifest,
    RedactedRecord,
    RedactionResult,
    TokenMap,
    all_specs,
    build_manifest,
    capture_git_commit,
    hash_record,
    hash_redaction_profile,
    hash_registered_kinds,
)

_RUN_A = "01900000-0000-7000-8000-0000000000a1"
_RUN_B = "01900000-0000-7000-8000-0000000000a2"
_PROC_EXPANDED = "01900000-0000-7000-8000-0000000000b1"
_PROC_DIRECT = "01900000-0000-7000-8000-0000000000b2"
_PROC_NO_RUN = "01900000-0000-7000-8000-0000000000b3"


def _stream_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "stream_type": "Procedure",
        "stream_id": _PROC_EXPANDED,
        "event_type": "ProcedureStarted",
        "schema_version": 1,
        "payload": {},
    }
    row.update(overrides)
    return row


def _procedure_registered(
    procedure_id: str, parent_run_id: str | None, *, schema_version: int = 1
) -> dict[str, object]:
    return _stream_row(
        stream_id=procedure_id,
        event_type="ProcedureRegistered",
        schema_version=schema_version,
        payload={"procedure_id": procedure_id, "parent_run_id": parent_run_id},
    )


def _recipe_expansion_recorded(procedure_id: str) -> dict[str, object]:
    return _stream_row(
        stream_id=procedure_id,
        event_type="RecipeExpansionRecorded",
        payload={"procedure_id": procedure_id},
    )


def _run_started(run_id: str) -> dict[str, object]:
    return _stream_row(stream_type="Run", stream_id=run_id, event_type="RunStarted", payload={})


def _record(*, watermark: int = 100) -> ExportedRecord:
    streams = (
        _run_started(_RUN_A),
        _run_started(_RUN_B),
        _procedure_registered(_PROC_EXPANDED, _RUN_A),
        _recipe_expansion_recorded(_PROC_EXPANDED),
        _procedure_registered(_PROC_DIRECT, _RUN_B),
        _procedure_registered(_PROC_NO_RUN, None),
        _procedure_registered("01900000-0000-7000-8000-0000000000b9", None, schema_version=2),
    )
    logbooks: dict[str, tuple[dict[str, object], ...]] = {
        "activity": ({"step_kind": "setpoint"}, {"step_kind": "check"}),
        "observation": ({"is_simulated": True}, {"is_simulated": True}),
    }
    return ExportedRecord(streams=streams, logbooks=logbooks, watermark=watermark)


def _matching_source_row_count_by_logbook_kind(record: ExportedRecord) -> dict[str, int]:
    """Every registered kind's `source_row_count`, set to agree with
    `record.logbooks`, for tests exercising something other than the
    independent count itself (most of this file)."""
    return {spec.kind: len(record.logbooks.get(spec.kind, ())) for spec in all_specs()}


def _build_manifest(record: ExportedRecord, **kwargs: object) -> Manifest:
    """`build_manifest`, defaulting `source_row_count_by_logbook_kind` to a mapping that
    agrees with `record.logbooks` for every registered kind, so the S2b
    independent-count check never fires incidentally in a test that isn't
    about it. Tests exercising that check call `build_manifest` directly
    with a hand-built, deliberately diverging (or missing) mapping."""
    kwargs.setdefault(
        "source_row_count_by_logbook_kind", _matching_source_row_count_by_logbook_kind(record)
    )
    return build_manifest(record, **kwargs)  # type: ignore[arg-type]


def test_exported_row_count_matches_each_kinds_length() -> None:
    """Per-kind `exported_row_count` (S2b) replaces the old top-level
    `row_count_by_logbook_kind` map, folded in because two per-kind count
    maps in one manifest agreed by construction with each other."""
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    counts = {
        kind: extent.exported_row_count for kind, extent in manifest.extent_by_logbook_kind.items()
    }
    assert counts["activity"] == 2
    assert counts["observation"] == 2
    assert counts["verdict"] == 0


def test_extent_by_logbook_kind_has_one_slot_per_registered_kind() -> None:
    """One mandatory slot per `all_specs()` kind, present even though this
    fixture's `record.logbooks` only carries two of the nine kinds:
    proof the enumeration comes from the registry, not from `record`."""
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert set(manifest.extent_by_logbook_kind) == {spec.kind for spec in all_specs()}


def test_envelope_driven_kinds_are_included_regardless_of_this_records_own_rows() -> None:
    """`activity` and `observation` are in this fixture's `record.logbooks`;
    `verdict`, `inference`, `diagnostic`, and `outcome` are not. Both
    groups are envelope-driven and must read `included` all the same:
    status is a registry fact, never derived from what THIS record
    happened to carry."""
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    for kind in ("verdict", "inference", "activity", "diagnostic", "outcome", "observation"):
        assert manifest.extent_by_logbook_kind[kind].status == LogbookKindExtentStatus.INCLUDED


async def _unused_reader(conn: asyncpg.Connection, scope_id: object) -> list[asyncpg.Record]:
    raise AssertionError("build_manifest must never call a spec's reader")


async def _unused_count_reader(conn: asyncpg.Connection) -> int:
    raise AssertionError("build_manifest must never call a spec's count_reader")


def test_kind_with_no_envelope_and_no_unscoped_reader_is_untraversed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No REGISTERED kind resolves `untraversed` in production any more:
    `heartbeat` (S5a), `capture_probe` (S5b) and `permit_probe` (S5c) all
    ended up wired with an `unscoped_reader`, alongside the six
    envelope-driven kinds. Constructed here rather than pinned against a
    real kind, per the trap this predicate would otherwise fall into once
    its last real example (`permit_probe`) stopped demonstrating it."""
    synthetic = EntriesTableSpec(
        kind="untraversed_test_kind",
        table="entries_untraversed_test_kind",
        envelope_class=None,
        scope_column="unused_id",
        scope_type=UUID,
        order_by=("event_id",),
        reader=_unused_reader,
        count_reader=_unused_count_reader,
    )
    monkeypatch.setattr(
        "cora.infrastructure.record_export._manifest.all_specs",
        lambda: (*all_specs(), synthetic),
    )
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert manifest.extent_by_logbook_kind["untraversed_test_kind"].status == (
        LogbookKindExtentStatus.UNTRAVERSED
    )


def test_heartbeat_is_included_via_its_unscoped_reader_despite_having_no_envelope() -> None:
    """S5a: `heartbeat` has no `*LogbookOpened` envelope, but its registry
    spec now declares an `unscoped_reader`, so the extent predicate ("does
    ANY reader reach this kind") must resolve it to `included` regardless
    of this fixture's own `record.logbooks`, which does not even carry a
    `heartbeat` entry."""
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert manifest.extent_by_logbook_kind["heartbeat"].status == LogbookKindExtentStatus.INCLUDED


def test_capture_probe_is_included_via_its_unscoped_reader_despite_having_no_envelope() -> None:
    """S5b: same predicate, same shape as heartbeat's test above, for
    `capture_probe`'s newly-wired `unscoped_reader`."""
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert manifest.extent_by_logbook_kind["capture_probe"].status == (
        LogbookKindExtentStatus.INCLUDED
    )


def test_permit_probe_is_included_via_its_unscoped_reader_despite_having_no_envelope() -> None:
    """S5c: same predicate, same shape as heartbeat's/capture_probe's tests
    above, for `permit_probe`'s newly-wired `unscoped_reader` -- the last
    of the three no-envelope kinds, so every registered kind now resolves
    `included` here."""
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert manifest.extent_by_logbook_kind["permit_probe"].status == (
        LogbookKindExtentStatus.INCLUDED
    )
    assert {extent.status for extent in manifest.extent_by_logbook_kind.values()} == {
        LogbookKindExtentStatus.INCLUDED
    }


def test_registered_kinds_hash_matches_hashing_all_specs_kinds_directly() -> None:
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert manifest.registered_kinds_hash == hash_registered_kinds(
        spec.kind for spec in all_specs()
    )


def test_registered_kinds_hash_is_insensitive_to_registry_iteration_order() -> None:
    """Independence from the registry's declaration order: a reader
    recomputing this hash from their own checkout's `all_specs()` must
    land on the same value regardless of iteration order."""
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    kinds = [spec.kind for spec in all_specs()]
    assert manifest.registered_kinds_hash == hash_registered_kinds(reversed(kinds))


def test_manifest_schema_version_matches_the_module_constant() -> None:
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert manifest.manifest_schema_version == MANIFEST_SCHEMA_VERSION


def test_max_schema_version_takes_the_max_per_event_type() -> None:
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    # Two ProcedureRegistered rows in the fixture: schema_version 1 (the
    # three _procedure_registered() calls) and 2 (the last row).
    assert manifest.max_schema_version_by_event_type["ProcedureRegistered"] == 2
    assert manifest.max_schema_version_by_event_type["RunStarted"] == 1


def test_is_simulated_true_when_every_observation_says_so() -> None:
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert manifest.is_simulated is True


def test_is_simulated_true_on_a_single_asserting_observation() -> None:
    """Matches `bool_or`: ANY row asserting simulated is enough, mixed or
    not. Renamed and flipped from `..._false_on_a_single_dissenting...`,
    which pinned the `all(...)` inversion this fix corrects."""
    record = ExportedRecord(
        streams=(),
        logbooks={"observation": ({"is_simulated": True}, {"is_simulated": False})},
    )
    manifest = _build_manifest(record, git_commit="deadbeef")
    assert manifest.is_simulated is True


def test_is_simulated_false_when_every_observation_says_otherwise() -> None:
    record = ExportedRecord(
        streams=(),
        logbooks={"observation": ({"is_simulated": False}, {"is_simulated": False})},
    )
    manifest = _build_manifest(record, git_commit="deadbeef")
    assert manifest.is_simulated is False


def test_is_simulated_vacuously_false_with_no_observations() -> None:
    """Matches the Run BC's `coalesce(bool_or(is_simulated), false)`
    identity for an empty window. Renamed and flipped from
    `..._vacuously_true_...`, which pinned the `all(...)` inversion this
    fix corrects: the first genuine beamline-attached export had zero
    observation rows and was reported simulated by that bug."""
    record = ExportedRecord(streams=(), logbooks={})
    manifest = _build_manifest(record, git_commit="deadbeef")
    assert manifest.is_simulated is False


def test_expansion_digest_present_only_for_the_run_whose_child_was_expanded() -> None:
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert manifest.expansion_digest_presence_by_run == {_RUN_A: True, _RUN_B: False}


def test_expansion_digest_ignores_procedures_with_no_parent_run() -> None:
    """_PROC_NO_RUN has parent_run_id=None; it must not create a phantom
    run entry or affect either real run's result."""
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert set(manifest.expansion_digest_presence_by_run) == {_RUN_A, _RUN_B}


def test_manifest_hashes_match_calling_the_hash_functions_directly() -> None:
    record = _record()
    manifest = _build_manifest(record, git_commit="deadbeef")
    assert manifest.record_hash == hash_record(record)
    assert manifest.redaction_profile_hash == hash_redaction_profile()


def test_manifest_carries_the_watermark_and_commit_verbatim() -> None:
    """`watermark` comes off `record.watermark`, not a separate parameter:
    it is the value `export_record` itself captured its query with."""
    manifest = _build_manifest(_record(watermark=4242), git_commit="cafef00d")
    assert manifest.watermark == 4242
    assert manifest.git_commit == "cafef00d"


def test_capture_git_commit_returns_a_full_sha() -> None:
    commit = capture_git_commit()
    assert re.fullmatch(r"[0-9a-f]{40}", commit)


def _redaction_result(
    record: ExportedRecord,
    *,
    unfired: frozenset[tuple[str, str, str]] = frozenset(),
    unfired_tier1: frozenset[tuple[str, str]] = frozenset(),
) -> RedactionResult:
    """A `RedactionResult` wrapping `record`'s own content unchanged, for
    tests that only exercise `build_manifest`'s H3 / unfired-clearances
    plumbing and do not need genuinely redacted (tokenized) content."""
    return RedactionResult(
        redacted_record=RedactedRecord(streams=record.streams, logbooks=record.logbooks),
        token_map=TokenMap(),
        unfired_tier2_clearances=unfired,
        unfired_tier1_fields=unfired_tier1,
    )


def test_unfired_tier2_clearances_absent_without_redaction() -> None:
    """`None` means no redaction happened, the same convention as
    `published_record_hash`; unrelated to whether any clearance would
    have fired."""
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert manifest.unfired_tier2_clearances is None


def test_unfired_tier2_clearances_empty_when_none_fired() -> None:
    """A `RedactionResult` whose `unfired_tier2_clearances` is empty
    reports an empty tuple, not `None`: redaction DID happen, so
    absence-as-signal no longer applies, and "empty" correctly reads as
    "nothing to report" rather than "not tracked"."""
    record = _record()
    manifest = _build_manifest(record, git_commit="deadbeef", redaction=_redaction_result(record))
    assert manifest.unfired_tier2_clearances == ()


def test_unfired_tier2_clearances_renders_sorted_kind_column_pointer() -> None:
    record = _record()
    manifest = _build_manifest(
        record,
        git_commit="deadbeef",
        redaction=_redaction_result(
            record,
            unfired=frozenset(
                {
                    ("activity", "payload", "units"),
                    ("activity", "payload", "channel"),
                }
            ),
        ),
    )
    assert manifest.unfired_tier2_clearances == (
        "activity/payload/channel",
        "activity/payload/units",
    )


def test_unfired_tier1_fields_absent_without_redaction() -> None:
    """Same `None`-means-no-redaction convention as `unfired_tier2_clearances`."""
    manifest = _build_manifest(_record(), git_commit="deadbeef")
    assert manifest.unfired_tier1_fields is None


def test_unfired_tier1_fields_empty_when_none_unfired() -> None:
    record = _record()
    manifest = _build_manifest(record, git_commit="deadbeef", redaction=_redaction_result(record))
    assert manifest.unfired_tier1_fields == ()


def test_unfired_tier1_fields_renders_sorted_event_type_field() -> None:
    record = _record()
    manifest = _build_manifest(
        record,
        git_commit="deadbeef",
        redaction=_redaction_result(
            record,
            unfired_tier1=frozenset(
                {
                    ("ProcedureRegistered", "kind"),
                    ("ProcedureRegistered", "capability_id"),
                }
            ),
        ),
    )
    assert manifest.unfired_tier1_fields == (
        "ProcedureRegistered/capability_id",
        "ProcedureRegistered/kind",
    )


def test_expansion_digest_presence_by_run_is_keyed_by_the_redactions_own_surrogate() -> None:
    """The published manifest must not carry the raw Run `stream_id` as a
    dict key: it must be the SAME surrogate `TokenMap.token_uuid` would
    hand back for that source, i.e. what tier-1 redaction already put on
    the run's own rows. Threading `token_map` through `redaction` rather
    than as an independent parameter makes it impossible to key by a
    DIFFERENT redaction's surrogates than the one that produced the
    streams body beside this manifest."""
    record = _record()
    redaction = _redaction_result(record)
    manifest = _build_manifest(record, git_commit="deadbeef", redaction=redaction)

    assert _RUN_A not in manifest.expansion_digest_presence_by_run
    assert _RUN_B not in manifest.expansion_digest_presence_by_run
    surrogate_a = redaction.token_map.token_uuid(_RUN_A)
    surrogate_b = redaction.token_map.token_uuid(_RUN_B)
    assert manifest.expansion_digest_presence_by_run == {surrogate_a: True, surrogate_b: False}


# --- S2b: the independent row count -----------------------------------
#
# `build_manifest` called directly here, never through `_build_manifest`:
# these tests are exactly about what a diverging or missing
# `source_row_count_by_logbook_kind` entry does, so the wrapper's auto-matching default
# would defeat the point.


def test_included_kind_with_matching_source_row_count_does_not_raise() -> None:
    record = _record()
    counts = _matching_source_row_count_by_logbook_kind(record)
    manifest = build_manifest(
        record, git_commit="deadbeef", source_row_count_by_logbook_kind=counts
    )
    extent = manifest.extent_by_logbook_kind["activity"]
    assert extent.source_row_count == 2
    assert extent.exported_row_count == 2


def test_included_kind_with_diverging_source_row_count_raises() -> None:
    """The omission-at-origin proof at the unit level: the database (as
    `source_row_count_by_logbook_kind` reports it) says 5 rows exist for `activity`, but
    the traversal only put 2 into `record.logbooks` -- exactly the shape
    of the defect this design exists to catch."""
    record = _record()
    counts = dict(_matching_source_row_count_by_logbook_kind(record))
    counts["activity"] = 5
    with pytest.raises(LogbookKindRowCountMismatchError) as excinfo:
        build_manifest(record, git_commit="deadbeef", source_row_count_by_logbook_kind=counts)
    assert excinfo.value.kind == "activity"
    assert excinfo.value.source_row_count == 5
    assert excinfo.value.exported_row_count == 2


def test_included_kind_absent_from_source_row_counts_raises() -> None:
    """A kind simply missing from the mapping (not merely `None`) must
    fail the same way as a genuine divergence: per
    `project_independent_check_principle.md`, a coverage field silently
    switched off by omission is the exact failure mode this check exists
    to close off, not a way to skip it."""
    record = _record()
    counts = dict(_matching_source_row_count_by_logbook_kind(record))
    del counts["activity"]
    with pytest.raises(LogbookKindRowCountMismatchError) as excinfo:
        build_manifest(record, git_commit="deadbeef", source_row_count_by_logbook_kind=counts)
    assert excinfo.value.kind == "activity"
    assert excinfo.value.source_row_count is None
    assert excinfo.value.exported_row_count == 2


def test_untraversed_kind_with_diverging_source_row_count_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reported, not compared: an `untraversed` kind's two counts may
    disagree wildly without raising. The converse invariant -- an
    `untraversed` kind MUST have zero rows actually present in the bundle
    -- belongs to S3's standalone verifier, which checks the bundle from
    outside; it is explicitly out of scope for this build-time check, per
    `project_record_completeness_design.md`'s S2b/S3 split."""
    synthetic = EntriesTableSpec(
        kind="untraversed_test_kind",
        table="entries_untraversed_test_kind",
        envelope_class=None,
        scope_column="unused_id",
        scope_type=UUID,
        order_by=("event_id",),
        reader=_unused_reader,
        count_reader=_unused_count_reader,
    )
    monkeypatch.setattr(
        "cora.infrastructure.record_export._manifest.all_specs",
        lambda: (*all_specs(), synthetic),
    )
    record = _record()
    counts = dict(_matching_source_row_count_by_logbook_kind(record))
    counts["untraversed_test_kind"] = 999
    manifest = build_manifest(
        record, git_commit="deadbeef", source_row_count_by_logbook_kind=counts
    )
    extent = manifest.extent_by_logbook_kind["untraversed_test_kind"]
    assert extent.status == LogbookKindExtentStatus.UNTRAVERSED
    assert extent.source_row_count == 999
    assert extent.exported_row_count == 0


def test_unscoped_kind_still_catches_a_render_stage_row_loss() -> None:
    """A cheap, mechanism-level check that `build_manifest`'s comparison
    doesn't special-case envelope-scoped kinds: handing it a
    `source_row_count_by_logbook_kind` that disagrees with a hand-built
    `record.logbooks` raises regardless of which kind's status predicate
    fired. It does NOT exercise `render_row`, `_export.py`'s fetch loop,
    or a real unscoped reader -- both sides here are supplied directly by
    this test, so by itself this cannot distinguish "the check works" from
    "the check is being asked the right question." The genuine, live proof
    that a row lost between a real unscoped fetch and the render stage
    still gets caught -- the one axis where an unscoped kind CAN
    genuinely diverge, since a DB-level divergence is structurally
    impossible for these three kinds under the shared-snapshot design --
    is `test_record_export_row_count_independence_postgres.py`'s
    `test_heartbeat_render_stage_row_loss_still_raises`, which seeds real
    rows, wraps the real `unscoped_reader`, and runs a real
    `export_bundle`."""
    record = ExportedRecord(
        streams=(),
        # The database holds 2 heartbeat rows (source_row_count_by_logbook_kind below);
        # only 1 made it into record.logbooks, simulating a row the
        # render stage lost after a correct, unscoped fetch.
        logbooks={"heartbeat": ({"run_id": "x"},)},
    )
    counts = dict(_matching_source_row_count_by_logbook_kind(record))
    counts["heartbeat"] = 2
    with pytest.raises(LogbookKindRowCountMismatchError) as excinfo:
        build_manifest(record, git_commit="deadbeef", source_row_count_by_logbook_kind=counts)
    assert excinfo.value.kind == "heartbeat"
