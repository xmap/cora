"""Unit tests for the `register_dataset` slice's pure decider.

Genesis-style decider: state must be None (otherwise
DatasetAlreadyExistsError); reason VOs validate the input;
cross-aggregate context refs validated against the command's
optional refs (existence-only per Q2 lock B).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_USED_CALIBRATIONS_MAX_ENTRIES,
    Dataset,
    DatasetAlreadyExistsError,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetUri,
    DerivedFromDatasetsNotFoundError,
    InvalidDatasetByteSizeError,
    InvalidDatasetChecksumError,
    InvalidDatasetEncodingError,
    InvalidDatasetNameError,
    InvalidDatasetUriError,
    InvalidDerivedFromError,
    InvalidUsedCalibrationsError,
    LinkedSubjectNotFoundError,
    ProducingProcedureNotFoundError,
    ProducingProcedureNotTerminalError,
    ProducingRunNotFoundError,
)
from cora.data.features import register_dataset
from cora.data.features.register_dataset import (
    DatasetRegistrationContext,
    RegisterDataset,
)
from cora.operation.aggregates.procedure import Procedure, ProcedureName, ProcedureStatus
from cora.run.aggregates.run import Run, RunName, RunStatus
from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import Subject, SubjectName

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000099"))


def _good_command(**overrides: object) -> RegisterDataset:
    base: dict[str, object] = {
        "name": "32-ID FlyScan recon",
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum_algorithm": "sha256",
        "checksum_value": _GOOD_SHA256,
        "byte_size": 1024,
        "media_type": "application/x-hdf5",
        "conforms_to": frozenset[str](),
        "producing_run_id": None,
        "subject_id": None,
        "derived_from": frozenset[UUID](),
    }
    base.update(overrides)
    return RegisterDataset(**base)  # type: ignore[arg-type]


def _existing_dataset() -> Dataset:
    return Dataset(
        id=uuid4(),
        name=DatasetName("seed"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
    )


def _fake_run() -> Run:
    return Run(
        id=uuid4(),
        name=RunName("seed-run"),
        plan_id=uuid4(),
        subject_id=uuid4(),
        status=RunStatus.RUNNING,
    )


def _fake_procedure(
    *,
    actuation_kind: str | None = None,
    status: ProcedureStatus = ProcedureStatus.COMPLETED,
) -> Procedure:
    return Procedure(
        id=uuid4(),
        name=ProcedureName("seed-procedure"),
        kind="alignment",
        status=status,
        actuation_kind=actuation_kind,
    )


def _fake_subject() -> Subject:
    return Subject(id=uuid4(), name=SubjectName("seed-subject"))


# ---------- Happy path ----------


@pytest.mark.unit
def test_decide_emits_dataset_registered_with_minimum_fields() -> None:
    new_id = uuid4()
    cmd = _good_command()
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=new_id,
        registered_by=_REGISTERED_BY,
    )
    assert len(events) == 1
    event = events[0]
    assert event.dataset_id == new_id
    assert event.name == "32-ID FlyScan recon"
    assert event.uri == "s3://aps-32id/runs/abc/recon.h5"
    assert event.checksum_algorithm == "sha256"
    assert event.checksum_value == _GOOD_SHA256
    assert event.byte_size == 1024
    assert event.media_type == "application/x-hdf5"
    assert event.conforms_to == frozenset()
    assert event.producing_run_id is None
    assert event.subject_id is None
    assert event.derived_from == frozenset()
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    cmd = _good_command(name="  trimmed  ")
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].name == "trimmed"


@pytest.mark.unit
def test_decide_trims_uri_via_value_object() -> None:
    cmd = _good_command(uri="  s3://b/k  ")
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].uri == "s3://b/k"


@pytest.mark.unit
def test_decide_accepts_zero_byte_size() -> None:
    cmd = _good_command(byte_size=0)
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].byte_size == 0


@pytest.mark.unit
def test_decide_accepts_encoding_conforms_to_set() -> None:
    cmd = _good_command(conforms_to=frozenset({"https://manual.nexusformat.org/"}))
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].conforms_to == frozenset({"https://manual.nexusformat.org/"})


# ---------- Field validation ----------


@pytest.mark.unit
def test_decide_raises_invalid_name_for_whitespace_only() -> None:
    cmd = _good_command(name="   ")
    with pytest.raises(InvalidDatasetNameError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_uri_for_missing_scheme() -> None:
    cmd = _good_command(uri="just-a-path")
    with pytest.raises(InvalidDatasetUriError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_checksum_for_md5() -> None:
    cmd = _good_command(checksum_algorithm="md5", checksum_value="d" * 32)
    with pytest.raises(InvalidDatasetChecksumError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_byte_size_for_negative() -> None:
    cmd = _good_command(byte_size=-1)
    with pytest.raises(InvalidDatasetByteSizeError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_encoding_for_empty_media_type() -> None:
    cmd = _good_command(media_type="")
    with pytest.raises(InvalidDatasetEncodingError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_derived_from_for_too_many_entries() -> None:
    cmd = _good_command(derived_from=frozenset(uuid4() for _ in range(65)))
    with pytest.raises(InvalidDerivedFromError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


# ---------- Cross-aggregate context ----------


@pytest.mark.unit
def test_decide_passes_when_producing_run_set_and_loaded() -> None:
    run = _fake_run()
    cmd = _good_command(producing_run_id=run.id)
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(producing_run=run),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].producing_run_id == run.id


@pytest.mark.unit
def test_decide_raises_when_producing_run_set_but_context_missing() -> None:
    """Defensive: if the handler skipped its load (or the load returned
    None), the decider raises rather than silently producing a dangling
    reference."""
    run_id = uuid4()
    cmd = _good_command(producing_run_id=run_id)
    with pytest.raises(ProducingRunNotFoundError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(producing_run=None),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_when_subject_set_but_context_missing() -> None:
    subject_id = uuid4()
    cmd = _good_command(subject_id=subject_id)
    with pytest.raises(LinkedSubjectNotFoundError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(subject=None),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_when_derived_from_missing_in_context() -> None:
    derived_a = uuid4()
    derived_b = uuid4()
    cmd = _good_command(derived_from=frozenset({derived_a, derived_b}))
    existing = _existing_dataset()
    # Context only has one of them.
    ctx = DatasetRegistrationContext(derived_from={derived_a: existing})
    with pytest.raises(DerivedFromDatasetsNotFoundError) as exc_info:
        register_dataset.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
    assert exc_info.value.missing_ids == [derived_b]


@pytest.mark.unit
def test_decide_passes_with_full_cross_agg_context() -> None:
    run = _fake_run()
    subject = _fake_subject()
    derived = _existing_dataset()
    cmd = _good_command(
        producing_run_id=run.id,
        subject_id=subject.id,
        derived_from=frozenset({derived.id}),
    )
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(
            producing_run=run,
            subject=subject,
            derived_from={derived.id: derived},
        ),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].producing_run_id == run.id
    assert events[0].subject_id == subject.id
    assert events[0].derived_from == frozenset({derived.id})


# ---------- Strict-not-idempotent ----------


@pytest.mark.unit
def test_decide_raises_already_exists_when_state_not_none() -> None:
    existing = _existing_dataset()
    with pytest.raises(DatasetAlreadyExistsError) as exc_info:
        register_dataset.decide(
            state=existing,
            command=_good_command(),
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
    assert exc_info.value.dataset_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    cmd = _good_command()
    first = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=new_id,
        registered_by=_REGISTERED_BY,
    )
    second = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=new_id,
        registered_by=_REGISTERED_BY,
    )
    assert first == second


# ---------- producing_run_end_state capture matrix ----------


def _fake_run_with_status(status: RunStatus) -> Run:
    return Run(
        id=uuid4(),
        name=RunName("seed-run"),
        plan_id=uuid4(),
        subject_id=uuid4(),
        status=status,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "run_status",
    [
        RunStatus.RUNNING,
        RunStatus.HELD,
        RunStatus.COMPLETED,
        RunStatus.ABORTED,
        RunStatus.STOPPED,
        RunStatus.TRUNCATED,
    ],
)
def test_decide_captures_producing_run_status_into_event_payload(
    run_status: RunStatus,
) -> None:
    """When producing_run is loaded, the decider captures
    its status.value into the DatasetRegistered event's
    `producing_run_end_state` field. The captured string is the
    SOLE input to the promote_dataset Run-must-be-Completed guard,
    so every Run lifecycle status must round-trip cleanly."""
    cmd = _good_command(producing_run_id=uuid4())
    run = _fake_run_with_status(run_status)
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(producing_run=run),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert len(events) == 1
    assert events[0].producing_run_end_state == run_status.value


@pytest.mark.unit
def test_decide_captures_none_end_state_when_no_producing_run() -> None:
    """Standalone-upload Datasets (no producing_run_id) get None
    producing_run_end_state. The promote_dataset Run-guard skips
    when this is None — so we pin the None branch explicitly."""
    cmd = _good_command()  # no producing_run_id
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),  # no producing_run loaded
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert len(events) == 1
    assert events[0].producing_run_end_state is None


@pytest.mark.unit
def test_decide_defaults_intent_to_trial_in_event_payload() -> None:
    """Every register_dataset event lands with intent='Trial'
    (default). Promotion is a separate explicit slice."""
    cmd = _good_command()
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].intent == "Trial"


# ---------- used_calibration_ids AsShot citation ----------


@pytest.mark.unit
def test_decide_defaults_used_calibration_ids_to_empty_tuple_on_event_payload() -> None:
    """Default command (no used_calibration_ids) lands an empty tuple
    on the event payload — uniform shape; readers without the new field
    fold via `payload.get("used_calibration_ids", [])` either way."""
    cmd = _good_command()
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].used_calibration_ids == ()


@pytest.mark.unit
def test_decide_threads_used_calibration_ids_through_to_event() -> None:
    """The decider threads the AsShot citation set verbatim from
    command to event (after sort-before-emit)."""
    cal_a = UUID("01900000-0000-7000-8000-00000000ca01")
    cal_b = UUID("01900000-0000-7000-8000-00000000ca02")
    cmd = _good_command(used_calibration_ids=frozenset({cal_a, cal_b}))
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert set(events[0].used_calibration_ids) == {cal_a, cal_b}


@pytest.mark.unit
def test_decide_sorts_used_calibration_ids_before_emit_for_deterministic_bytes() -> None:
    """Decider sorts the AsShot citation set so the
    event-payload bytes are deterministic regardless of frozenset
    iteration order (mirrors Run.pinned_calibration_ids decider-time
    treatment + derived_from sorted-list precedent)."""
    cal_a = UUID("01900000-0000-7000-8000-00000000ca01")
    cal_b = UUID("01900000-0000-7000-8000-00000000ca02")
    cal_c = UUID("01900000-0000-7000-8000-00000000ca03")
    cmd = _good_command(used_calibration_ids=frozenset({cal_c, cal_a, cal_b}))
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    # The decider emits sorted by UUID natural ordering — pin the
    # exact tuple order (NOT just set equality) to defend against
    # a future refactor dropping the sort.
    assert events[0].used_calibration_ids == (cal_a, cal_b, cal_c)


@pytest.mark.unit
def test_decide_raises_invalid_used_calibration_ids_for_too_many_entries() -> None:
    """Cardinality cap: more than DATASET_USED_CALIBRATIONS_MAX_ENTRIES
    raises. Mirrors derived_from cardinality cap; same shape, same
    error-class precedent."""
    too_many = frozenset(uuid4() for _ in range(DATASET_USED_CALIBRATIONS_MAX_ENTRIES + 1))
    cmd = _good_command(used_calibration_ids=too_many)
    with pytest.raises(InvalidUsedCalibrationsError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_accepts_used_calibration_ids_at_cardinality_cap() -> None:
    """Boundary: exactly at the cap is accepted (off-by-one guard)."""
    exactly_at_cap = frozenset(uuid4() for _ in range(DATASET_USED_CALIBRATIONS_MAX_ENTRIES))
    cmd = _good_command(used_calibration_ids=exactly_at_cap)
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert len(events[0].used_calibration_ids) == DATASET_USED_CALIBRATIONS_MAX_ENTRIES


@pytest.mark.unit
def test_decide_does_not_cross_bc_validate_used_calibration_ids() -> None:
    """Eventual-consistency stance per
    [[project_calibration_design]] anti-hook #3: the write path
    does NOT look up the CalibrationRevision ids; any well-formed
    UUID set under the cardinality cap is accepted. Fully-synthetic
    pin ids that will never exist in any Calibration BC stream
    pass validation."""
    synthetic = frozenset(uuid4() for _ in range(5))
    cmd = _good_command(used_calibration_ids=synthetic)
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert len(events) == 1
    assert set(events[0].used_calibration_ids) == synthetic


@pytest.mark.unit
def test_decide_does_not_compare_used_calibration_ids_against_producing_run() -> None:
    """The decider does NOT compare the Dataset's used_calibration_ids
    against producing_run.pinned_calibration_ids. The two sets are
    independent (Git-blob-reference analog; "partial override" is a
    category error in the revision-cited atomic-ID model). The
    decider trusts what command supplies, even when the cited
    revisions are different from anything the producing Run
    pinned."""
    cal_dataset_only = UUID("01900000-0000-7000-8000-00000cd00001")
    cmd = _good_command(
        producing_run_id=uuid4(),
        used_calibration_ids=frozenset({cal_dataset_only}),
    )
    fake_run = _fake_run()
    # The Run pre-loaded in context has its own pinned_calibration_ids
    # (irrelevant to this slice's decider, since we do NOT compare).
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(producing_run=fake_run),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].used_calibration_ids == (cal_dataset_only,)


# ---------- actuation kind derivation (from the producing Procedure) ----------


@pytest.mark.unit
def test_decide_derives_actuation_kind_from_producing_procedure() -> None:
    """The kind is DERIVED server-side from the loaded Procedure's terminal
    state and snapshotted onto DatasetRegistered (the promote gate reads it
    later). It is never a caller input."""
    procedure = _fake_procedure(actuation_kind="Simulated")
    events = register_dataset.decide(
        state=None,
        command=_good_command(producing_procedure_id=procedure.id),
        context=DatasetRegistrationContext(producing_procedure=procedure),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].producing_actuation_kind == "Simulated"
    assert events[0].producing_procedure_id == procedure.id


@pytest.mark.unit
def test_decide_defaults_actuation_kind_to_none_without_producing_procedure() -> None:
    """A registration with no producing Procedure (external upload) records
    None for both the procedure ref and the kind, leaving the gate inactive."""
    events = register_dataset.decide(
        state=None,
        command=_good_command(),
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].producing_procedure_id is None
    assert events[0].producing_actuation_kind is None


@pytest.mark.unit
@pytest.mark.parametrize("status", [ProcedureStatus.DEFINED, ProcedureStatus.RUNNING])
def test_decide_rejects_non_terminal_producing_procedure(status: ProcedureStatus) -> None:
    """Registering against a non-terminal producing Procedure is rejected: its
    actuation kind isn't final yet, so the snapshot would be a stale None
    (item-6 option A). Only terminal Procedures may be named."""
    procedure = _fake_procedure(actuation_kind=None, status=status)
    with pytest.raises(ProducingProcedureNotTerminalError) as exc:
        register_dataset.decide(
            state=None,
            command=_good_command(producing_procedure_id=procedure.id),
            context=DatasetRegistrationContext(producing_procedure=procedure),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
    assert exc.value.current_status == status.value


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [ProcedureStatus.COMPLETED, ProcedureStatus.ABORTED, ProcedureStatus.TRUNCATED]
)
def test_decide_derives_none_kind_from_terminal_procedure_that_recorded_none(
    status: ProcedureStatus,
) -> None:
    """A terminal Procedure that recorded no kind (no routing table / cancelled
    / truncated) derives None at register -- allowed here; the promote gate
    blocks it later as unproven provenance."""
    procedure = _fake_procedure(actuation_kind=None, status=status)
    events = register_dataset.decide(
        state=None,
        command=_good_command(producing_procedure_id=procedure.id),
        context=DatasetRegistrationContext(producing_procedure=procedure),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].producing_procedure_id == procedure.id
    assert events[0].producing_actuation_kind is None


@pytest.mark.unit
def test_decide_raises_when_producing_procedure_set_but_context_missing() -> None:
    """Decider-level statement of the handler's contract: a set
    producing_procedure_id with no loaded Procedure raises (mirrors the
    producing_run guard)."""
    procedure_id = uuid4()
    with pytest.raises(ProducingProcedureNotFoundError):
        register_dataset.decide(
            state=None,
            command=_good_command(producing_procedure_id=procedure_id),
            context=DatasetRegistrationContext(producing_procedure=None),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
