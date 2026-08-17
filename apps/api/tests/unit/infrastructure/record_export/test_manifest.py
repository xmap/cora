"""Unit tests for the export manifest.

`build_manifest` is pure (no I/O): every input is passed in, so these
tests construct synthetic `ExportedRecord`s directly rather than going
through a live database. The DB-backed acceptance path (via a real
Procedure + Run) lives in
`tests/integration/test_record_export_manifest_postgres.py`.
"""

import re

from cora.infrastructure.record_export import (
    MANIFEST_SCHEMA_VERSION,
    ExportedRecord,
    LogbookKindExtentStatus,
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


def test_logbook_row_counts_match_each_kinds_length() -> None:
    manifest = build_manifest(_record(), git_commit="deadbeef")
    assert manifest.row_count_by_logbook_kind == {"activity": 2, "observation": 2}


def test_extent_by_logbook_kind_has_one_slot_per_registered_kind() -> None:
    """One mandatory slot per `all_specs()` kind, present even though this
    fixture's `record.logbooks` only carries two of the nine kinds:
    proof the enumeration comes from the registry, not from `record`."""
    manifest = build_manifest(_record(), git_commit="deadbeef")
    assert set(manifest.extent_by_logbook_kind) == {spec.kind for spec in all_specs()}


def test_envelope_driven_kinds_are_included_regardless_of_this_records_own_rows() -> None:
    """`activity` and `observation` are in this fixture's `record.logbooks`;
    `verdict`, `inference`, `diagnostic`, and `outcome` are not. Both
    groups are envelope-driven and must read `included` all the same:
    status is a registry fact, never derived from what THIS record
    happened to carry."""
    manifest = build_manifest(_record(), git_commit="deadbeef")
    for kind in ("verdict", "inference", "activity", "diagnostic", "outcome", "observation"):
        assert manifest.extent_by_logbook_kind[kind].status == LogbookKindExtentStatus.INCLUDED


def test_kinds_with_no_envelope_are_untraversed() -> None:
    manifest = build_manifest(_record(), git_commit="deadbeef")
    for kind in ("heartbeat", "permit_probe", "capture_probe"):
        assert manifest.extent_by_logbook_kind[kind].status == LogbookKindExtentStatus.UNTRAVERSED


def test_registered_kinds_hash_matches_hashing_all_specs_kinds_directly() -> None:
    manifest = build_manifest(_record(), git_commit="deadbeef")
    assert manifest.registered_kinds_hash == hash_registered_kinds(
        spec.kind for spec in all_specs()
    )


def test_registered_kinds_hash_is_insensitive_to_registry_iteration_order() -> None:
    """Independence from the registry's declaration order: a reader
    recomputing this hash from their own checkout's `all_specs()` must
    land on the same value regardless of iteration order."""
    manifest = build_manifest(_record(), git_commit="deadbeef")
    kinds = [spec.kind for spec in all_specs()]
    assert manifest.registered_kinds_hash == hash_registered_kinds(reversed(kinds))


def test_manifest_schema_version_matches_the_module_constant() -> None:
    manifest = build_manifest(_record(), git_commit="deadbeef")
    assert manifest.manifest_schema_version == MANIFEST_SCHEMA_VERSION


def test_max_schema_version_takes_the_max_per_event_type() -> None:
    manifest = build_manifest(_record(), git_commit="deadbeef")
    # Two ProcedureRegistered rows in the fixture: schema_version 1 (the
    # three _procedure_registered() calls) and 2 (the last row).
    assert manifest.max_schema_version_by_event_type["ProcedureRegistered"] == 2
    assert manifest.max_schema_version_by_event_type["RunStarted"] == 1


def test_is_simulated_true_when_every_observation_says_so() -> None:
    manifest = build_manifest(_record(), git_commit="deadbeef")
    assert manifest.is_simulated is True


def test_is_simulated_true_on_a_single_asserting_observation() -> None:
    """Matches `bool_or`: ANY row asserting simulated is enough, mixed or
    not. Renamed and flipped from `..._false_on_a_single_dissenting...`,
    which pinned the `all(...)` inversion this fix corrects."""
    record = ExportedRecord(
        streams=(),
        logbooks={"observation": ({"is_simulated": True}, {"is_simulated": False})},
    )
    manifest = build_manifest(record, git_commit="deadbeef")
    assert manifest.is_simulated is True


def test_is_simulated_false_when_every_observation_says_otherwise() -> None:
    record = ExportedRecord(
        streams=(),
        logbooks={"observation": ({"is_simulated": False}, {"is_simulated": False})},
    )
    manifest = build_manifest(record, git_commit="deadbeef")
    assert manifest.is_simulated is False


def test_is_simulated_vacuously_false_with_no_observations() -> None:
    """Matches the Run BC's `coalesce(bool_or(is_simulated), false)`
    identity for an empty window. Renamed and flipped from
    `..._vacuously_true_...`, which pinned the `all(...)` inversion this
    fix corrects: the first genuine beamline-attached export had zero
    observation rows and was reported simulated by that bug."""
    record = ExportedRecord(streams=(), logbooks={})
    manifest = build_manifest(record, git_commit="deadbeef")
    assert manifest.is_simulated is False


def test_expansion_digest_present_only_for_the_run_whose_child_was_expanded() -> None:
    manifest = build_manifest(_record(), git_commit="deadbeef")
    assert manifest.expansion_digest_presence_by_run == {_RUN_A: True, _RUN_B: False}


def test_expansion_digest_ignores_procedures_with_no_parent_run() -> None:
    """_PROC_NO_RUN has parent_run_id=None; it must not create a phantom
    run entry or affect either real run's result."""
    manifest = build_manifest(_record(), git_commit="deadbeef")
    assert set(manifest.expansion_digest_presence_by_run) == {_RUN_A, _RUN_B}


def test_manifest_hashes_match_calling_the_hash_functions_directly() -> None:
    record = _record()
    manifest = build_manifest(record, git_commit="deadbeef")
    assert manifest.record_hash == hash_record(record)
    assert manifest.redaction_profile_hash == hash_redaction_profile()


def test_manifest_carries_the_watermark_and_commit_verbatim() -> None:
    """`watermark` comes off `record.watermark`, not a separate parameter:
    it is the value `export_record` itself captured its query with."""
    manifest = build_manifest(_record(watermark=4242), git_commit="cafef00d")
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
    manifest = build_manifest(_record(), git_commit="deadbeef")
    assert manifest.unfired_tier2_clearances is None


def test_unfired_tier2_clearances_empty_when_none_fired() -> None:
    """A `RedactionResult` whose `unfired_tier2_clearances` is empty
    reports an empty tuple, not `None`: redaction DID happen, so
    absence-as-signal no longer applies, and "empty" correctly reads as
    "nothing to report" rather than "not tracked"."""
    record = _record()
    manifest = build_manifest(record, git_commit="deadbeef", redaction=_redaction_result(record))
    assert manifest.unfired_tier2_clearances == ()


def test_unfired_tier2_clearances_renders_sorted_kind_column_pointer() -> None:
    record = _record()
    manifest = build_manifest(
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
    manifest = build_manifest(_record(), git_commit="deadbeef")
    assert manifest.unfired_tier1_fields is None


def test_unfired_tier1_fields_empty_when_none_unfired() -> None:
    record = _record()
    manifest = build_manifest(record, git_commit="deadbeef", redaction=_redaction_result(record))
    assert manifest.unfired_tier1_fields == ()


def test_unfired_tier1_fields_renders_sorted_event_type_field() -> None:
    record = _record()
    manifest = build_manifest(
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
    manifest = build_manifest(record, git_commit="deadbeef", redaction=redaction)

    assert _RUN_A not in manifest.expansion_digest_presence_by_run
    assert _RUN_B not in manifest.expansion_digest_presence_by_run
    surrogate_a = redaction.token_map.token_uuid(_RUN_A)
    surrogate_b = redaction.token_map.token_uuid(_RUN_B)
    assert manifest.expansion_digest_presence_by_run == {surrogate_a: True, surrogate_b: False}
