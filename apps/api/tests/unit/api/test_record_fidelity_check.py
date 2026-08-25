"""Unit tests for the D6 record-fidelity operator command.

`check_record_fidelity` needs a real Postgres connection for the
`full/`-vs-live comparison, so the end-to-end acceptance path lives in
`tests/integration/test_record_fidelity_check_postgres.py`. What is
testable without a database -- the CLI surface, row parsing, state
rendering, the pure fold-and-hash pipeline, and the summary counters --
is covered here.

The mutation tests at the bottom are the load-bearing ones: a fidelity
check is worth nothing until the WRONG bundle has been run through it
and shown to fail. Each mutation is narrowed to change exactly one
thing, so a failure localizes to what actually broke.
"""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cora.api.record_fidelity_check import (
    _fold_run,  # pyright: ignore[reportPrivateUsage]
    _full_summary,  # pyright: ignore[reportPrivateUsage]
    _published_summary,  # pyright: ignore[reportPrivateUsage]
    _render_run_state,  # pyright: ignore[reportPrivateUsage]
    _row_slices_by_run_id,  # pyright: ignore[reportPrivateUsage]
    _run_state_hash,  # pyright: ignore[reportPrivateUsage]
    _RunResult,  # pyright: ignore[reportPrivateUsage]
    _stored_event_from_row,  # pyright: ignore[reportPrivateUsage]
    build_parser,
)
from cora.infrastructure.record_export import render_value
from cora.run.aggregates.run import (
    LOGBOOK_KIND_OBSERVATION,
    OBSERVATION_LOGBOOK_SCHEMA,
    ConductMode,
    RunCompleted,
    RunObservationLogbookOpened,
    RunStarted,
    RunStatus,
    event_type_name,
    to_payload,
)
from cora.shared.identifier import Identifier

_NOW = datetime(2026, 8, 18, 9, 0, 0, tzinfo=UTC)


def _row(
    *,
    stream_id: UUID,
    version: int,
    event_type: str,
    payload: dict[str, object],
    position: int,
    transaction_id: object = "100",
) -> dict[str, object]:
    """Build one `streams.jsonl` row exactly as the exporter renders it:
    UUID -> str, datetime -> UTC ISO, `payload` already JSON-primitive.
    `transaction_id` defaults to the FULL bundle's string shape; pass an
    int to model a published row."""
    return {
        "position": position,
        "event_id": str(uuid4()),
        "stream_type": "Run",
        "stream_id": render_value(stream_id),
        "version": version,
        "event_type": event_type,
        "schema_version": 1,
        "payload": payload,
        "metadata": {},
        "correlation_id": str(uuid4()),
        "causation_id": None,
        "principal_id": None,
        "occurred_at": render_value(_NOW),
        "recorded_at": render_value(_NOW),
        "signature": None,
        "signature_kid": None,
        "signature_version": None,
        "transaction_id": transaction_id,
    }


def _run_rows(run_id: UUID) -> list[dict[str, object]]:
    """A minimal, real Run stream: started (Witnessed, one external ref),
    an observation logbook opened, then completed. Built from the
    actual domain events via `to_payload`, not hand-typed dicts, so a
    payload-shape drift in the real event classes surfaces here too."""
    started = RunStarted(
        run_id=run_id,
        name="2bmb commissioning scan",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        conduct_mode=ConductMode.WITNESSED,
        external_refs=({"scheme": "capture-code", "value": "2bmb-tomoscan"},),
    )
    logbook_id = uuid4()
    opened = RunObservationLogbookOpened(
        run_id=run_id,
        logbook_id=logbook_id,
        kind=LOGBOOK_KIND_OBSERVATION,
        schema=OBSERVATION_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    completed = RunCompleted(run_id=run_id, occurred_at=_NOW, observed_at=_NOW)
    return [
        _row(
            stream_id=run_id,
            version=1,
            event_type=event_type_name(started),
            payload=to_payload(started),
            position=1,
        ),
        _row(
            stream_id=run_id,
            version=2,
            event_type=event_type_name(opened),
            payload=to_payload(opened),
            position=2,
        ),
        _row(
            stream_id=run_id,
            version=3,
            event_type=event_type_name(completed),
            payload=to_payload(completed),
            position=3,
        ),
    ]


def test_build_parser_requires_a_bundle_root_positional() -> None:
    args = build_parser().parse_args(["/tmp/some-bundle"])
    assert str(args.bundle_root) == "/tmp/some-bundle"
    assert args.json_out is None


def test_build_parser_accepts_json_out() -> None:
    args = build_parser().parse_args(["/tmp/some-bundle", "--json-out", "/tmp/out.json"])
    assert str(args.json_out) == "/tmp/out.json"


def test_row_slices_by_run_id_filters_non_run_stream_types() -> None:
    run_id = uuid4()
    rows = _run_rows(run_id)
    foreign = dict(rows[0])
    foreign["stream_type"] = "Procedure"

    slices = _row_slices_by_run_id([*rows, foreign])

    assert set(slices) == {str(run_id)}
    assert len(slices[str(run_id)]) == 3


def test_row_slices_by_run_id_preserves_file_order_per_run() -> None:
    """File order is `ORDER BY transaction_id, position` and is
    load-bearing for `fold`; grouping must never re-sort it."""
    run_id = uuid4()
    rows = _run_rows(run_id)

    slices = _row_slices_by_run_id(rows)

    assert [row["event_type"] for row in slices[str(run_id)]] == [
        "RunStarted",
        "RunObservationLogbookOpened",
        "RunCompleted",
    ]


def test_stored_event_from_row_parses_a_full_bundle_row() -> None:
    run_id = uuid4()
    row = _run_rows(run_id)[0]

    stored = _stored_event_from_row(row)

    assert stored.stream_id == run_id
    assert stored.event_type == "RunStarted"
    assert stored.transaction_id == 100
    assert stored.occurred_at == _NOW
    assert stored.metadata == {}
    assert stored.signature is None


def test_stored_event_from_row_parses_a_published_shaped_row() -> None:
    """A published row has no `metadata` / `signature*` keys at all and
    a densified INT `transaction_id`, not the full bundle's string."""
    run_id = uuid4()
    row = _run_rows(run_id)[0]
    del row["metadata"]
    del row["signature"]
    del row["signature_kid"]
    del row["signature_version"]
    row["transaction_id"] = 1

    stored = _stored_event_from_row(row)

    assert stored.metadata == {}
    assert stored.signature is None
    assert stored.transaction_id == 1


def test_fold_run_folds_a_real_run_stream() -> None:
    run_id = uuid4()
    run, fold_ms, error = _fold_run(_run_rows(run_id))

    assert error is None
    assert fold_ms >= 0.0
    assert run is not None
    assert run.id == run_id
    assert run.status == RunStatus.COMPLETED
    assert run.conduct_mode == ConductMode.WITNESSED
    assert run.external_refs == frozenset(
        {Identifier(scheme="capture-code", value="2bmb-tomoscan")}
    )


def test_fold_run_reports_an_unknown_event_type_as_a_refold_error_not_a_traceback() -> None:
    run_id = uuid4()
    rows = _run_rows(run_id)
    rows[0]["event_type"] = "SomeEventThisAggregateNeverHad"

    run, _fold_ms, error = _fold_run(rows)

    assert run is None
    assert error is not None
    assert "SomeEventThisAggregateNeverHad" in error


def test_render_run_state_reflects_status_not_only_identity() -> None:
    """The whole point of NOT using `content_subset()`'s exclusion list:
    two states of the same run that differ only in `status` must hash
    differently."""
    run_id = uuid4()
    rows = _run_rows(run_id)
    running, _ms, _err = _fold_run(rows[:1])
    completed, _ms2, _err2 = _fold_run(rows)
    assert running is not None
    assert completed is not None

    assert _render_run_state(running)["status"] != _render_run_state(completed)["status"]
    assert _run_state_hash(running) != _run_state_hash(completed)


def test_run_state_hash_is_none_for_none() -> None:
    assert _run_state_hash(None) is None


def test_run_result_as_json_carries_the_figure_contract_superset() -> None:
    result = _RunResult(
        run_id="abc",
        event_count=3,
        fold_ms=1.5,
        actuation_kind=None,
        state_hash_recorded="h1",
        state_hash_refolded="h1",
        digests_match=True,
        refold_error=None,
    )
    body = result.as_json()
    assert body["steps_hash_recorded"] is None
    assert body["bindings_hash_recorded"] is None
    assert body["state_hash_recorded"] == "h1"
    assert body["digests_match"] is True
    assert body["worked_example"] is False


def test_full_summary_counts_matched_and_mismatched() -> None:
    results = [
        _RunResult("a", 1, 0.0, None, "h", "h", True, None),
        _RunResult("b", 1, 0.0, None, "h1", "h2", False, None),
        _RunResult("c", 1, 0.0, None, None, None, None, "boom"),
    ]
    summary = _full_summary(results)
    assert summary.runs == 3
    assert summary.refolded == 2
    assert summary.matched == 1
    assert summary.mismatched == 1
    assert summary.unrefolded == 1
    assert "mismatched=1" in summary.render()


def test_published_summary_never_reports_a_match_count() -> None:
    results = [
        _RunResult("a", 1, 0.0, None, None, "h", None, None),
        _RunResult("b", 1, 0.0, None, None, None, None, "tier-1 dropped a required field"),
    ]
    summary = _published_summary(results)
    assert summary.matched is None
    assert summary.mismatched is None
    assert summary.refolded == 1
    assert summary.unrefolded == 1
    assert "tokenized" in summary.render()


# --- Mutation tests -----------------------------------------------------
#
# Per the repo's own "assert the invariant by mutation" lesson: a check is
# worth nothing until the WRONG bundle has been run through it. Each
# mutation below is narrowed to exactly one change.


def test_mutation_control_unmutated_slice_folds_and_hashes_deterministically() -> None:
    """Not a mutation: proves the harness itself is not always-red before
    trusting the mutations below to mean anything."""
    run_id = uuid4()
    rows = _run_rows(run_id)
    run_a, _ms_a, err_a = _fold_run(rows)
    run_b, _ms_b, err_b = _fold_run(rows)
    assert err_a is None
    assert err_b is None
    assert _run_state_hash(run_a) == _run_state_hash(run_b)


def test_mutation_reordering_two_rows_changes_the_outcome() -> None:
    run_id = uuid4()
    rows = _run_rows(run_id)
    baseline_hash = _run_state_hash(_fold_run(rows)[0])

    reordered = [rows[1], rows[0], rows[2]]
    reordered_run, _ms, error = _fold_run(reordered)

    # RunObservationLogbookOpened before RunStarted has no prior state to
    # transition from, so the evolver itself refuses it -- exactly the
    # signal a reordered export slice should produce.
    assert reordered_run is None
    assert error is not None
    assert baseline_hash is not None


def test_mutation_dropping_the_terminal_row_changes_the_hash() -> None:
    run_id = uuid4()
    rows = _run_rows(run_id)
    baseline_hash = _run_state_hash(_fold_run(rows)[0])

    dropped_hash = _run_state_hash(_fold_run(rows[:-1])[0])

    assert baseline_hash != dropped_hash


def test_mutation_tampering_a_payload_scalar_changes_the_hash() -> None:
    run_id = uuid4()
    rows = _run_rows(run_id)
    baseline_hash = _run_state_hash(_fold_run(rows)[0])

    tampered = [dict(row) for row in rows]
    tampered[0] = dict(tampered[0])
    original_payload = cast("dict[str, object]", tampered[0]["payload"])
    tampered_payload: dict[str, object] = {
        **original_payload,
        "name": "a different run name entirely",
    }
    tampered[0]["payload"] = tampered_payload
    tampered_hash = _run_state_hash(_fold_run(tampered)[0])

    assert baseline_hash != tampered_hash


def test_mutation_empty_slice_is_reported_unrefolded_never_matched() -> None:
    run, _ms, error = _fold_run([])
    assert run is None
    assert error == "fold produced no state"
