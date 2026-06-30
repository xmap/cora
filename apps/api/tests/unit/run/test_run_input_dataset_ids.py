"""Unit tests for Run.input_dataset_ids (PROV `used` input Dataset refs).

Mirrors the pinned_calibration_ids suite: the field flows from the
start_run decider through RunStarted, to_payload, from_stored, and the
evolver fold onto Run.input_dataset_ids. NO cross-BC existence check is
exercised here (id-only atomic refs, cross-BC eventual-consistency
stance); only set cardinality is validated. The start_run gate that
reads each input Dataset's Verified Distribution lands separately and
goes through the Data BC.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLifecycle,
    AssetName,
    AssetTier,
)
from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult
from cora.infrastructure.ports.dataset_distribution_lookup import (
    DatasetDistributionLookupResult,
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.plan import Plan, PlanName, PlanStatus
from cora.run.aggregates.run import (
    RUN_INPUT_DATASETS_MAX_ENTRIES,
    InvalidInputDatasetsError,
    fold,
    validate_input_dataset_ids,
)
from cora.run.aggregates.run.events import RunStarted, from_stored, to_payload
from cora.run.features import start_run
from cora.run.features.start_run import RunStartContext, StartRun
from cora.subject.aggregates.subject import Subject, SubjectName, SubjectStatus

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _active_clearance_stub() -> tuple[ClearanceLookupResult, ...]:
    return (
        ClearanceLookupResult(
            clearance_id=UUID(int=0),
            status="Active",
            template_id=UUID(int=1),
            template_code="ESAF",
            facility_code="aps",
        ),
    )


def _plan(*, asset_ids: frozenset[UUID]) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("Reconstruction"),
        practice_id=uuid4(),
        asset_ids=asset_ids,
        status=PlanStatus.DEFINED,
    )


def _asset(*, asset_id: UUID, family_ids: frozenset[UUID]) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("ComputeNode"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        family_ids=family_ids,
    )


def _subject() -> Subject:
    return Subject(
        id=uuid4(),
        name=SubjectName("PorousCeramicSample-A"),
        status=SubjectStatus.MOUNTED,
    )


def _verified(dataset_id: UUID) -> DatasetDistributionLookupResult:
    return DatasetDistributionLookupResult(
        distribution_id=uuid4(),
        dataset_id=dataset_id,
        supply_id=uuid4(),
        status="Verified",
    )


def _context(
    *, input_dataset_ids: frozenset[UUID] = frozenset()
) -> tuple[RunStartContext, UUID, Subject]:
    """Build a context that passes every start_run gate. Each id in
    `input_dataset_ids` is seeded with a Verified Distribution so the
    genesis input gate passes (these tests pin field threading +
    cardinality, not the gate itself; see
    test_start_run_input_gate_decider.py for the gate)."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    subject = _subject()
    context = RunStartContext(
        plan=plan,
        subject=subject,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
        input_distributions={ds: (_verified(ds),) for ds in input_dataset_ids},
    )
    return context, cap, subject


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Run",
        stream_id=uuid4(),  # type: ignore[arg-type]
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- validate_input_dataset_ids ----------


@pytest.mark.unit
def test_validate_input_dataset_ids_accepts_empty() -> None:
    """Empty ref set is the default (Run with no input Datasets)."""
    assert validate_input_dataset_ids(frozenset()) == frozenset()


@pytest.mark.unit
def test_validate_input_dataset_ids_accepts_within_cap() -> None:
    """A reasonable-size ref set (under the cap) is accepted verbatim,
    with no element-level existence check at this layer."""
    s = frozenset(uuid4() for _ in range(10))
    assert validate_input_dataset_ids(s) == s


@pytest.mark.unit
def test_validate_input_dataset_ids_accepts_exactly_at_cap() -> None:
    """Boundary: exactly RUN_INPUT_DATASETS_MAX_ENTRIES is accepted
    (off-by-one guard mirrors the pinned_calibration_ids boundary)."""
    s = frozenset(uuid4() for _ in range(RUN_INPUT_DATASETS_MAX_ENTRIES))
    assert validate_input_dataset_ids(s) == s


@pytest.mark.unit
def test_validate_input_dataset_ids_rejects_over_cap() -> None:
    """Cardinality cap rejects > RUN_INPUT_DATASETS_MAX_ENTRIES; raises
    InvalidInputDatasetsError. Mirrors the pinned_calibration_ids cap
    exactly (same precedent + same default cap of 64)."""
    s = frozenset(uuid4() for _ in range(RUN_INPUT_DATASETS_MAX_ENTRIES + 1))
    with pytest.raises(InvalidInputDatasetsError):
        validate_input_dataset_ids(s)


@pytest.mark.unit
def test_invalid_input_datasets_error_carries_count() -> None:
    """The error class exposes `.count` for observability + debugging
    (matches the pinned_calibration_ids error contract)."""
    bad_count = RUN_INPUT_DATASETS_MAX_ENTRIES + 5
    err = InvalidInputDatasetsError(bad_count)
    assert err.count == bad_count
    assert str(bad_count) in str(err)


# ---------- event serialization ----------


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_input_dataset_ids_sorted() -> None:
    """The wire form is a list sorted lexicographically for deterministic
    byte ordering (the in-memory frozenset has no order)."""
    ds_a = UUID("01900000-0000-7000-8000-0000000d5001")
    ds_b = UUID("01900000-0000-7000-8000-0000000d5002")
    ds_c = UUID("01900000-0000-7000-8000-0000000d5003")
    event = RunStarted(
        run_id=uuid4(),
        name="Reconstruction consuming three input Datasets",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        input_dataset_ids=(ds_c, ds_a, ds_b),
    )
    payload = to_payload(event)
    assert payload["input_dataset_ids"] == sorted([str(ds_a), str(ds_b), str(ds_c)])


@pytest.mark.unit
def test_to_payload_always_renders_input_dataset_ids_key_when_empty() -> None:
    """Run has no content-hash so the key is rendered unconditionally;
    an empty input set serializes as `[]`, not an omitted key."""
    event = RunStarted(
        run_id=uuid4(),
        name="Run without input Datasets",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["input_dataset_ids"] == []


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_input_dataset_ids_key_as_empty() -> None:
    """Forward-compat: legacy RunStarted payloads have no
    input_dataset_ids key. from_stored returns an empty tuple via
    `payload.get(..., [])`."""
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(uuid4()),
            "name": "Legacy run",
            "plan_id": str(uuid4()),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: no "input_dataset_ids" key, legacy shape.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.input_dataset_ids == ()


@pytest.mark.unit
def test_run_started_input_dataset_ids_round_trip() -> None:
    """RunStarted with input_dataset_ids round-trips through to_payload +
    from_stored. The event class holds them as a tuple; to_payload sorts
    before serialise so already-sorted input round-trips trivially."""
    ds_a = UUID("01900000-0000-7000-8000-0000000d5001")
    ds_b = UUID("01900000-0000-7000-8000-0000000d5002")
    original = RunStarted(
        run_id=uuid4(),
        name="Run with input Datasets",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        input_dataset_ids=(ds_a, ds_b),
    )
    stored = _stored("RunStarted", to_payload(original))
    assert from_stored(stored) == original


# ---------- end-to-end fold ----------


@pytest.mark.unit
def test_input_dataset_ids_flow_decider_to_run_state_as_frozenset() -> None:
    """End-to-end: decider -> RunStarted -> to_payload -> from_stored ->
    fold -> Run.input_dataset_ids as a frozenset (in-memory equality)."""
    ds_a = uuid4()
    ds_b = uuid4()
    context, cap, subject = _context(input_dataset_ids=frozenset({ds_a, ds_b}))
    new_id = uuid4()
    decision = start_run.decide(
        state=None,
        command=StartRun(
            name="Reconstruction",
            plan_id=context.plan.id,
            subject_id=subject.id,
            input_dataset_ids=frozenset({ds_a, ds_b}),
        ),
        context=context,
        needed_family_ids_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=new_id,
    )
    event = decision.run_events[0]
    rebuilt = from_stored(_stored("RunStarted", to_payload(event)))
    state = fold([rebuilt])
    assert state is not None
    assert state.input_dataset_ids == frozenset({ds_a, ds_b})


# ---------- decider threading + cardinality ----------


@pytest.mark.unit
def test_decide_defaults_input_dataset_ids_to_empty_when_omitted() -> None:
    """Ref set defaults to empty frozenset; emitted event payload is `()`."""
    context, cap, subject = _context()
    decision = start_run.decide(
        state=None,
        command=StartRun(name="Run", plan_id=context.plan.id, subject_id=subject.id),
        context=context,
        needed_family_ids_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert decision.run_events[0].input_dataset_ids == ()


@pytest.mark.unit
def test_decide_threads_input_dataset_ids_sorted_through_to_event() -> None:
    """The decider sorts the operator-supplied frozenset before emit so
    the event payload has deterministic bytes."""
    ds_a = uuid4()
    ds_b = uuid4()
    ds_c = uuid4()
    context, cap, subject = _context(input_dataset_ids=frozenset({ds_a, ds_b, ds_c}))
    decision = start_run.decide(
        state=None,
        command=StartRun(
            name="Reconstruction",
            plan_id=context.plan.id,
            subject_id=subject.id,
            input_dataset_ids=frozenset({ds_c, ds_a, ds_b}),
        ),
        context=context,
        needed_family_ids_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert decision.run_events[0].input_dataset_ids == tuple(sorted([ds_a, ds_b, ds_c]))


@pytest.mark.unit
def test_decide_rejects_input_dataset_ids_over_cap() -> None:
    """Cardinality cap on the input Dataset ref set. Symmetric to the
    pinned_calibration_ids decider rejecting > 64 entries."""
    context, cap, subject = _context()
    too_many = frozenset(uuid4() for _ in range(RUN_INPUT_DATASETS_MAX_ENTRIES + 1))
    with pytest.raises(InvalidInputDatasetsError):
        start_run.decide(
            state=None,
            command=StartRun(
                name="Too many input Datasets",
                plan_id=context.plan.id,
                subject_id=subject.id,
                input_dataset_ids=too_many,
            ),
            context=context,
            needed_family_ids_snapshot=frozenset({cap}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_accepts_input_dataset_ids_exactly_at_cap() -> None:
    """Boundary guard: exactly at the cap is accepted (off-by-one mirror
    of the pinned_calibration_ids boundary test)."""
    at_cap = frozenset(uuid4() for _ in range(RUN_INPUT_DATASETS_MAX_ENTRIES))
    context, cap, subject = _context(input_dataset_ids=at_cap)
    decision = start_run.decide(
        state=None,
        command=StartRun(
            name="Cap input Datasets",
            plan_id=context.plan.id,
            subject_id=subject.id,
            input_dataset_ids=at_cap,
        ),
        context=context,
        needed_family_ids_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(decision.run_events[0].input_dataset_ids) == RUN_INPUT_DATASETS_MAX_ENTRIES
