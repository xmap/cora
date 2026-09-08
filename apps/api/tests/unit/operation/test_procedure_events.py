"""Procedure event (de)serialization + roundtrip tests."""

import dataclasses
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.record_export._redact_tier1 import redact_tier1_payload
from cora.infrastructure.record_export._tokens import TokenMap
from cora.operation.aggregates.procedure import (
    DIAGNOSTIC_LOGBOOK_SCHEMA,
    OUTCOME_LOGBOOK_SCHEMA,
    STEPS_LOGBOOK_SCHEMA,
    ProcedureAborted,
    ProcedureActivitiesLogbookOpened,
    ProcedureCompleted,
    ProcedureDiagnosticLogbookOpened,
    ProcedureHeld,
    ProcedureIterationEnded,
    ProcedureIterationStarted,
    ProcedureOutcomeLogbookOpened,
    ProcedureRegistered,
    ProcedureResumed,
    ProcedureStarted,
    ProcedureTerminationReason,
    ProcedureTruncated,
    RecipeExpansionRecorded,
    SteeringDesignRecorded,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.shared.decision_signals import DecisionConfidenceSource
from cora.shared.logbook import LogbookFieldSpec, LogbookSchema
from cora.shared.steering import (
    BoTorchBrain,
    GridWalkBrain,
    InMemoryBrain,
    LlmBrain,
    SobolBrain,
    StagedBrain,
    SteeringAxis,
    SteeringBrain,
    SteeringDesignSource,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
    SteeringSubstrate,
)

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Procedure",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_event_type_name_for_procedure_registered() -> None:
    event = ProcedureRegistered(
        procedure_id=uuid4(),
        name="X",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ProcedureRegistered"


@pytest.mark.unit
def test_to_payload_serializes_procedure_registered_to_primitives() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000a001")
    asset1 = UUID("01900000-0000-7000-8000-00000000a002")
    asset2 = UUID("01900000-0000-7000-8000-00000000a003")
    parent_run = UUID("01900000-0000-7000-8000-00000000a004")
    event = ProcedureRegistered(
        procedure_id=procedure_id,
        name="2-BM rotation-axis alignment",
        kind="alignment",
        target_asset_ids=(asset2, asset1),  # unsorted input
        parent_run_id=parent_run,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "procedure_id": str(procedure_id),
        "name": "2-BM rotation-axis alignment",
        "kind": "alignment",
        # Sorted by string form for deterministic payload bytes.
        "target_asset_ids": sorted([str(asset1), str(asset2)]),
        "parent_run_id": str(parent_run),
        # capability_id (default). Pre-binding streams omit the key
        # and fold via `.get("capability_id")` in from_stored.
        "capability_id": None,
        # recipe_id (default). Pre-Recipe-rewrite streams omit the
        # key and fold via `.get("recipe_id")` in from_stored.
        # `register_procedure_from_recipe` sets both `recipe_id` and
        # the denorm `capability_id`; the legacy `register_procedure`
        # slice leaves both None.
        "recipe_id": None,
        # Patience cap (default None). Legacy streams omit the key and
        # fold via `.get("max_consecutive_unconverged_iterations")`.
        "max_consecutive_unconverged_iterations": None,
        # Declared beam need (default Required). Pre-slice streams omit
        # the key and fold to Required, so an old Procedure replays
        # against the strict gate rather than inheriting an exemption.
        "beam_requirement": "Required",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_standalone_procedure_with_null_parent() -> None:
    """Standalone procedures (bakeouts, etc.) have parent_run_id=None."""
    event = ProcedureRegistered(
        procedure_id=uuid4(),
        name="Vessel-A bakeout",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["parent_run_id"] is None
    assert payload["target_asset_ids"] == []


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_registered() -> None:
    procedure_id = uuid4()
    asset1 = uuid4()
    parent_run = uuid4()
    stored = _stored(
        "ProcedureRegistered",
        {
            "procedure_id": str(procedure_id),
            "name": "X",
            "kind": "bakeout",
            "target_asset_ids": [str(asset1)],
            "parent_run_id": str(parent_run),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureRegistered)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.name == "X"
    assert rebuilt.kind == "bakeout"
    assert rebuilt.target_asset_ids == (asset1,)
    assert rebuilt.parent_run_id == parent_run


@pytest.mark.unit
def test_from_stored_rebuilds_standalone_procedure_with_null_parent() -> None:
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureRegistered",
        {
            "procedure_id": str(procedure_id),
            "name": "Vessel-A bakeout",
            "kind": "bakeout",
            "target_asset_ids": [],
            "parent_run_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureRegistered)
    assert rebuilt.parent_run_id is None
    assert rebuilt.target_asset_ids == ()


@pytest.mark.unit
def test_from_stored_rebuilds_legacy_procedure_registered_without_capability_id_key() -> None:
    """Additive backwards-compat pin: legacy streams omit
    the `capability_id` key from `ProcedureRegistered` payloads
    entirely. `from_stored` MUST use `payload.get("capability_id")`
    sentinel-default-None so legacy streams fold cleanly without
    backfill. Mirrors the additive-evolution shape locked for
    Method.capability_id and Method.needed_supplies."""
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureRegistered",
        {
            # NOTE: NO "capability_id" key — legacy shape.
            "procedure_id": str(procedure_id),
            "name": "Vessel-A bakeout",
            "kind": "bakeout",
            "target_asset_ids": [],
            "parent_run_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureRegistered)
    assert rebuilt.capability_id is None


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_registered_with_capability_id() -> None:
    """Additive evolution: current streams carry `capability_id` as a
    UUID string in the payload; `from_stored` converts it back to a
    UUID instance in the rebuilt event."""
    procedure_id = uuid4()
    capability_id = uuid4()
    stored = _stored(
        "ProcedureRegistered",
        {
            "procedure_id": str(procedure_id),
            "name": "Hexapod reboot",
            "kind": "recovery",
            "target_asset_ids": [],
            "parent_run_id": None,
            "capability_id": str(capability_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureRegistered)
    assert rebuilt.capability_id == capability_id


@pytest.mark.unit
def test_procedure_registered_round_trips() -> None:
    asset1 = uuid4()
    asset2 = uuid4()
    parent_run = uuid4()
    original = ProcedureRegistered(
        procedure_id=uuid4(),
        name="2-BM rotation-axis alignment",
        kind="alignment",
        target_asset_ids=(asset1, asset2),
        parent_run_id=parent_run,
        occurred_at=_NOW,
    )
    stored = _stored("ProcedureRegistered", to_payload(original))
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureRegistered)
    # Sets equal: payload sorts; from_stored preserves payload order.
    assert set(rebuilt.target_asset_ids) == set(original.target_asset_ids)
    assert rebuilt.procedure_id == original.procedure_id
    assert rebuilt.parent_run_id == original.parent_run_id


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    stored = _stored("BogusEvent", {})
    with pytest.raises(ValueError, match="Unknown ProcedureEvent event_type"):
        from_stored(stored)


# --- 10c-b transition events ---


@pytest.mark.unit
def test_event_type_name_for_procedure_started() -> None:
    event = ProcedureStarted(procedure_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "ProcedureStarted"


@pytest.mark.unit
def test_event_type_name_for_procedure_completed() -> None:
    event = ProcedureCompleted(procedure_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "ProcedureCompleted"


@pytest.mark.unit
def test_event_type_name_for_procedure_aborted() -> None:
    event = ProcedureAborted(procedure_id=uuid4(), reason="x", occurred_at=_NOW)
    assert event_type_name(event) == "ProcedureAborted"


@pytest.mark.unit
def test_to_payload_serializes_procedure_started() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000b001")
    event = ProcedureStarted(procedure_id=procedure_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "procedure_id": str(procedure_id),
        "occurred_at": _NOW.isoformat(),
        # Beam bookkeeping defaults: an event constructed without them
        # reports the strict requirement and no observation.
        "beam_requirement": "Required",
        "beam_state_at_start": None,
    }


@pytest.mark.unit
def test_to_payload_serializes_procedure_completed() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000b002")
    event = ProcedureCompleted(procedure_id=procedure_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "procedure_id": str(procedure_id),
        "occurred_at": _NOW.isoformat(),
        "actuation_kind": None,
        "termination_reason": None,
    }


@pytest.mark.unit
def test_to_payload_serializes_procedure_completed_with_actuation_kind() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000b012")
    event = ProcedureCompleted(
        procedure_id=procedure_id, occurred_at=_NOW, actuation_kind="Simulated"
    )
    assert to_payload(event)["actuation_kind"] == "Simulated"


@pytest.mark.unit
def test_to_payload_serializes_procedure_completed_with_termination_reason() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000b014")
    event = ProcedureCompleted(
        procedure_id=procedure_id,
        occurred_at=_NOW,
        termination_reason=ProcedureTerminationReason.BUDGET_WALL_CLOCK_EXHAUSTED,
    )
    assert to_payload(event)["termination_reason"] == "BudgetWallClockExhausted"


@pytest.mark.unit
def test_to_payload_serializes_procedure_aborted() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000b003")
    event = ProcedureAborted(procedure_id=procedure_id, reason="quench", occurred_at=_NOW)
    assert to_payload(event) == {
        "procedure_id": str(procedure_id),
        "reason": "quench",
        "occurred_at": _NOW.isoformat(),
        "actuation_kind": None,
    }


@pytest.mark.unit
def test_to_payload_serializes_procedure_aborted_with_actuation_kind() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000b013")
    event = ProcedureAborted(
        procedure_id=procedure_id, reason="quench", occurred_at=_NOW, actuation_kind="Hybrid"
    )
    assert to_payload(event)["actuation_kind"] == "Hybrid"


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_started() -> None:
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureStarted",
        {"procedure_id": str(procedure_id), "occurred_at": _NOW.isoformat()},
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureStarted)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.occurred_at == _NOW


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_completed() -> None:
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureCompleted",
        {"procedure_id": str(procedure_id), "occurred_at": _NOW.isoformat()},
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureCompleted)
    assert rebuilt.procedure_id == procedure_id


@pytest.mark.unit
def test_from_stored_procedure_completed_legacy_payload_folds_actuation_kind_to_none() -> None:
    """Pre-activation ProcedureCompleted payloads omit actuation_kind; they
    must fold to None, not raise."""
    stored = _stored(
        "ProcedureCompleted",
        {"procedure_id": str(uuid4()), "occurred_at": _NOW.isoformat()},
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureCompleted)
    assert rebuilt.actuation_kind is None


@pytest.mark.unit
def test_from_stored_procedure_completed_reads_actuation_kind() -> None:
    stored = _stored(
        "ProcedureCompleted",
        {
            "procedure_id": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
            "actuation_kind": "Simulated",
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureCompleted)
    assert rebuilt.actuation_kind == "Simulated"


@pytest.mark.unit
def test_from_stored_procedure_completed_legacy_payload_folds_termination_reason_to_none() -> None:
    """Pre-budget-enforcement ProcedureCompleted payloads omit
    termination_reason; they must fold to None, not raise."""
    stored = _stored(
        "ProcedureCompleted",
        {"procedure_id": str(uuid4()), "occurred_at": _NOW.isoformat()},
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureCompleted)
    assert rebuilt.termination_reason is None


@pytest.mark.unit
def test_from_stored_procedure_completed_reads_termination_reason() -> None:
    stored = _stored(
        "ProcedureCompleted",
        {
            "procedure_id": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
            "termination_reason": "BudgetIterationsExhausted",
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureCompleted)
    assert rebuilt.termination_reason is ProcedureTerminationReason.BUDGET_ITERATIONS_EXHAUSTED


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_aborted() -> None:
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureAborted",
        {
            "procedure_id": str(procedure_id),
            "reason": "vacuum loss",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureAborted)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.reason == "vacuum loss"
    assert rebuilt.actuation_kind is None


@pytest.mark.unit
def test_from_stored_procedure_aborted_reads_actuation_kind() -> None:
    stored = _stored(
        "ProcedureAborted",
        {
            "procedure_id": str(uuid4()),
            "reason": "vacuum loss",
            "occurred_at": _NOW.isoformat(),
            "actuation_kind": "Hybrid",
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureAborted)
    assert rebuilt.actuation_kind == "Hybrid"


@pytest.mark.unit
def test_procedure_started_round_trips() -> None:
    original = ProcedureStarted(procedure_id=uuid4(), occurred_at=_NOW)
    stored = _stored("ProcedureStarted", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_procedure_completed_round_trips() -> None:
    original = ProcedureCompleted(procedure_id=uuid4(), occurred_at=_NOW)
    stored = _stored("ProcedureCompleted", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_procedure_aborted_round_trips() -> None:
    original = ProcedureAborted(procedure_id=uuid4(), reason="hardware fault", occurred_at=_NOW)
    stored = _stored("ProcedureAborted", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


# --- ProcedureActivitiesLogbookOpened (lazy-open envelope) ---


@pytest.mark.unit
def test_event_type_name_for_procedure_steps_logbook_opened() -> None:
    event = ProcedureActivitiesLogbookOpened(
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        kind="steps",
        schema=STEPS_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ProcedureActivitiesLogbookOpened"


@pytest.mark.unit
def test_to_payload_serializes_procedure_steps_logbook_opened() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000c001")
    logbook_id = UUID("01900000-0000-7000-8000-00000000c002")
    schema = LogbookSchema(
        fields={"step_kind": LogbookFieldSpec(type="string")},
        description="test",
    )
    event = ProcedureActivitiesLogbookOpened(
        procedure_id=procedure_id,
        logbook_id=logbook_id,
        kind="steps",
        schema=schema,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["procedure_id"] == str(procedure_id)
    assert payload["logbook_id"] == str(logbook_id)
    assert payload["kind"] == "steps"
    assert payload["schema"] == schema.to_dict()
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_steps_logbook_opened() -> None:
    procedure_id = uuid4()
    logbook_id = uuid4()
    schema = STEPS_LOGBOOK_SCHEMA
    stored = _stored(
        "ProcedureActivitiesLogbookOpened",
        {
            "procedure_id": str(procedure_id),
            "logbook_id": str(logbook_id),
            "kind": "steps",
            "schema": schema.to_dict(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureActivitiesLogbookOpened)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.logbook_id == logbook_id
    assert rebuilt.kind == "steps"
    assert rebuilt.schema == schema


@pytest.mark.unit
def test_procedure_steps_logbook_opened_round_trips() -> None:
    original = ProcedureActivitiesLogbookOpened(
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        kind="steps",
        schema=STEPS_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    stored = _stored("ProcedureActivitiesLogbookOpened", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


# --- ProcedureDiagnosticLogbookOpened (lazy-open envelope) ---


@pytest.mark.unit
def test_event_type_name_for_procedure_diagnostic_logbook_opened() -> None:
    event = ProcedureDiagnosticLogbookOpened(
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        kind="diagnostic",
        schema=DIAGNOSTIC_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ProcedureDiagnosticLogbookOpened"


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_diagnostic_logbook_opened() -> None:
    procedure_id = uuid4()
    logbook_id = uuid4()
    stored = _stored(
        "ProcedureDiagnosticLogbookOpened",
        {
            "procedure_id": str(procedure_id),
            "logbook_id": str(logbook_id),
            "kind": "diagnostic",
            "schema": DIAGNOSTIC_LOGBOOK_SCHEMA.to_dict(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureDiagnosticLogbookOpened)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.logbook_id == logbook_id
    assert rebuilt.kind == "diagnostic"
    assert rebuilt.schema == DIAGNOSTIC_LOGBOOK_SCHEMA


@pytest.mark.unit
def test_procedure_diagnostic_logbook_opened_round_trips() -> None:
    original = ProcedureDiagnosticLogbookOpened(
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        kind="diagnostic",
        schema=DIAGNOSTIC_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    stored = _stored("ProcedureDiagnosticLogbookOpened", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


# --- ProcedureOutcomeLogbookOpened (lazy-open envelope) ---


@pytest.mark.unit
def test_event_type_name_for_procedure_outcome_logbook_opened() -> None:
    event = ProcedureOutcomeLogbookOpened(
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        kind="outcome",
        schema=OUTCOME_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ProcedureOutcomeLogbookOpened"


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_outcome_logbook_opened() -> None:
    procedure_id = uuid4()
    logbook_id = uuid4()
    stored = _stored(
        "ProcedureOutcomeLogbookOpened",
        {
            "procedure_id": str(procedure_id),
            "logbook_id": str(logbook_id),
            "kind": "outcome",
            "schema": OUTCOME_LOGBOOK_SCHEMA.to_dict(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureOutcomeLogbookOpened)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.logbook_id == logbook_id
    assert rebuilt.kind == "outcome"
    assert rebuilt.schema == OUTCOME_LOGBOOK_SCHEMA


@pytest.mark.unit
def test_procedure_outcome_logbook_opened_round_trips() -> None:
    original = ProcedureOutcomeLogbookOpened(
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        kind="outcome",
        schema=OUTCOME_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    stored = _stored("ProcedureOutcomeLogbookOpened", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


# --- ProcedureTruncated (partial-data terminal) ---


@pytest.mark.unit
def test_event_type_name_for_procedure_truncated() -> None:
    event = ProcedureTruncated(
        procedure_id=uuid4(),
        reason="weekend power loss",
        interrupted_at=_NOW,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ProcedureTruncated"


@pytest.mark.unit
def test_to_payload_serializes_procedure_truncated_with_interrupted_at() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000d001")
    interrupted_at = _NOW - timedelta(hours=2)
    event = ProcedureTruncated(
        procedure_id=procedure_id,
        reason="vacuum loss",
        interrupted_at=interrupted_at,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "procedure_id": str(procedure_id),
        "reason": "vacuum loss",
        "interrupted_at": interrupted_at.isoformat(),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_procedure_truncated_with_null_interrupted_at() -> None:
    """interrupted_at is optional; None serializes as null."""
    event = ProcedureTruncated(
        procedure_id=uuid4(),
        reason="unknown when crashed",
        interrupted_at=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["interrupted_at"] is None


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_truncated_with_interrupted_at() -> None:
    procedure_id = uuid4()
    interrupted_at = _NOW - timedelta(hours=3)
    stored = _stored(
        "ProcedureTruncated",
        {
            "procedure_id": str(procedure_id),
            "reason": "hardware fault",
            "interrupted_at": interrupted_at.isoformat(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureTruncated)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.reason == "hardware fault"
    assert rebuilt.interrupted_at == interrupted_at


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_truncated_with_null_interrupted_at() -> None:
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureTruncated",
        {
            "procedure_id": str(procedure_id),
            "reason": "unknown",
            "interrupted_at": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureTruncated)
    assert rebuilt.interrupted_at is None


@pytest.mark.unit
def test_procedure_truncated_round_trips() -> None:
    original = ProcedureTruncated(
        procedure_id=uuid4(),
        reason="weekend power loss",
        interrupted_at=_NOW - timedelta(hours=12),
        occurred_at=_NOW,
    )
    stored = _stored("ProcedureTruncated", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_to_payload_bindings_field_is_dict_after_canonical_json_hoist() -> None:
    """The events.py `to_payload(RecipeExpansionRecorded)` arm uses
    `json.loads(canonical_json_bytes(dict(bindings)))` so the persisted
    payload `bindings` field stays a dict (the shape `from_stored`'s
    `dict(payload['bindings'])` consumer expects). A future refactor
    that drops the `json.loads(...)` wrapper (e.g., `.decode('utf-8')`)
    would persist a JSON string and break round-trip; this test pins
    the dict shape.
    """
    event = RecipeExpansionRecorded(
        procedure_id=uuid4(),
        recipe_id=uuid4(),
        recipe_version="v1",
        capability_id=uuid4(),
        capability_version=None,
        bindings={"beta": 2.0, "alpha": 1.0},
        expansion_port_version="v1",
        steps_hash="aaaa",
        bindings_hash="bbbb",
        step_count=1,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert isinstance(payload["bindings"], dict)
    assert payload["bindings"] == {"alpha": 1.0, "beta": 2.0}
    rebuilt = from_stored(_stored("RecipeExpansionRecorded", payload))
    assert rebuilt.bindings == event.bindings  # type: ignore[union-attr]


@pytest.mark.unit
def test_procedure_registered_round_trips_with_patience_cap() -> None:
    event = ProcedureRegistered(
        procedure_id=uuid4(),
        name="2-BM center alignment",
        kind="center_alignment",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
        max_consecutive_unconverged_iterations=5,
    )
    payload = to_payload(event)
    assert payload["max_consecutive_unconverged_iterations"] == 5
    assert from_stored(_stored("ProcedureRegistered", payload)) == event


@pytest.mark.unit
def test_from_stored_folds_legacy_procedure_registered_without_cap_key_to_none() -> None:
    event = ProcedureRegistered(
        procedure_id=uuid4(),
        name="legacy",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    del payload["max_consecutive_unconverged_iterations"]  # pre-cap stream
    assert from_stored(_stored("ProcedureRegistered", payload)) == event


@pytest.mark.unit
def test_event_type_name_returns_iteration_boundary_class_names() -> None:
    started = ProcedureIterationStarted(procedure_id=uuid4(), iteration_index=1, occurred_at=_NOW)
    ended = ProcedureIterationEnded(
        procedure_id=uuid4(), iteration_index=1, converged=True, reason=None, occurred_at=_NOW
    )
    assert event_type_name(started) == "ProcedureIterationStarted"
    assert event_type_name(ended) == "ProcedureIterationEnded"


@pytest.mark.unit
def test_to_payload_serializes_iteration_started() -> None:
    pid = uuid4()
    payload = to_payload(
        ProcedureIterationStarted(procedure_id=pid, iteration_index=4, occurred_at=_NOW)
    )
    assert payload == {
        "procedure_id": str(pid),
        "iteration_index": 4,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("converged", "reason"),
    [(True, "within tolerance"), (False, None), (None, None)],
)
def test_to_payload_serializes_iteration_ended(converged: bool | None, reason: str | None) -> None:
    pid = uuid4()
    payload = to_payload(
        ProcedureIterationEnded(
            procedure_id=pid,
            iteration_index=2,
            converged=converged,
            reason=reason,
            occurred_at=_NOW,
        )
    )
    assert payload == {
        "procedure_id": str(pid),
        "iteration_index": 2,
        "converged": converged,
        "reason": reason,
        "occurred_at": _NOW.isoformat(),
        "advised_stop": None,
        "reasoning": None,
        "confidence": None,
        "confidence_source": None,
        "alternatives": [],
        "model_ref": None,
        "advised_next_point": None,
        "advice_latency_ms": None,
    }


@pytest.mark.unit
def test_iteration_started_round_trips() -> None:
    event = ProcedureIterationStarted(procedure_id=uuid4(), iteration_index=7, occurred_at=_NOW)
    rebuilt = from_stored(_stored("ProcedureIterationStarted", to_payload(event)))
    assert rebuilt == event


@pytest.mark.unit
@pytest.mark.parametrize(
    ("converged", "reason"),
    [(True, "ok"), (False, "off by 2px"), (None, None)],
)
def test_iteration_ended_round_trips(converged: bool | None, reason: str | None) -> None:
    event = ProcedureIterationEnded(
        procedure_id=uuid4(),
        iteration_index=3,
        converged=converged,
        reason=reason,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("ProcedureIterationEnded", to_payload(event)))
    assert rebuilt == event


@pytest.mark.unit
def test_iteration_ended_round_trips_with_advised_next_point() -> None:
    """A steered iteration's recorded advised coordinate survives the round trip."""
    event = ProcedureIterationEnded(
        procedure_id=uuid4(),
        iteration_index=2,
        converged=None,
        reason=None,
        occurred_at=_NOW,
        advised_stop=False,
        model_ref="botorch",
        advised_next_point={"energy": 7.2, "gap": 3.1},
    )
    payload = to_payload(event)
    assert payload["advised_next_point"] == {"energy": 7.2, "gap": 3.1}
    rebuilt = from_stored(_stored("ProcedureIterationEnded", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_iteration_ended_round_trips_with_every_field_set() -> None:
    """No field of the iteration carrier is dropped by to_payload.

    The other round-trip tests above leave most optional fields at their
    defaults, so `rebuilt == event` passes even when `to_payload` forgets one:
    None serializes to absent and deserializes back to None, and the equality
    holds for the wrong reason. That is how `advice_latency_ms` was added to
    the dataclass, the decider, the projection and the read surface while
    `to_payload` silently dropped it, with the whole unit suite green.

    This fixture sets EVERY field to a non-default value, and the assertion
    below refuses to let it drift back: if someone adds a field and does not
    populate it here, the guard fails rather than going quietly blind.
    """
    event = ProcedureIterationEnded(
        procedure_id=uuid4(),
        iteration_index=7,
        converged=False,
        reason="off by 2px",
        occurred_at=_NOW,
        advised_stop=True,
        reasoning="the posterior mean flattened",
        confidence=0.62,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=("keep going",),
        model_ref="botorch",
        advised_next_point={"energy": 7.2, "gap": 3.1},
        advice_latency_ms=1234.5,
    )

    # The fixture must exercise every field, or the equality below is vacuous
    # for whichever field was left alone.
    defaults = {
        f.name: f.default
        for f in dataclasses.fields(ProcedureIterationEnded)
        if f.default is not dataclasses.MISSING
    }
    at_default = [name for name, default in defaults.items() if getattr(event, name) == default]
    assert at_default == [], f"fixture leaves fields at their default: {at_default}"

    rebuilt = from_stored(_stored("ProcedureIterationEnded", to_payload(event)))
    assert rebuilt == event


@pytest.mark.unit
def test_iteration_ended_pre_tier1_stream_folds_advised_next_point_to_none() -> None:
    """A payload written before advised_next_point existed deserializes to None."""
    event = ProcedureIterationEnded(
        procedure_id=uuid4(),
        iteration_index=1,
        converged=True,
        reason=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    del payload["advised_next_point"]  # simulate a pre-TIER-1 stream
    rebuilt = from_stored(_stored("ProcedureIterationEnded", payload))
    assert isinstance(rebuilt, ProcedureIterationEnded)
    assert rebuilt.advised_next_point is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureCompleted",
        "ProcedureAborted",
        "ProcedureTruncated",
        "ProcedureHeld",
        "ProcedureResumed",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureIterationStarted",
        "ProcedureIterationEnded",
        "SteeringDesignRecorded",
    ],
)
def test_from_stored_raises_on_malformed_payload(event_type: str) -> None:
    """Per the convention adopted post-corpus-survey (Marten /
    pyeventsourcing / Pydantic / msgspec all wrap), each event-type case
    wraps `KeyError`/`TypeError`/`AttributeError` into a tagged
    `ValueError` so a corrupted event row fails loud with the event-type
    name in the message rather than bubbling a raw KeyError from deep
    in the load path."""
    with pytest.raises(ValueError, match=f"Malformed {event_type} payload"):
        from_stored(_stored(event_type, {}))


# --- ProcedureHeld / ProcedureResumed (resumable conduct, Tier 1) ---


@pytest.mark.unit
def test_event_type_names_for_hold_resume() -> None:
    held = ProcedureHeld(procedure_id=uuid4(), reason="pause", occurred_at=_NOW)
    resumed = ProcedureResumed(procedure_id=uuid4(), re_establishment_boundary=0, occurred_at=_NOW)
    assert event_type_name(held) == "ProcedureHeld"
    assert event_type_name(resumed) == "ProcedureResumed"


@pytest.mark.unit
def test_to_payload_serializes_procedure_held() -> None:
    pid = uuid4()
    decision_id = uuid4()
    payload = to_payload(
        ProcedureHeld(
            procedure_id=pid,
            reason="beam dropped",
            decided_by_decision_id=decision_id,
            occurred_at=_NOW,
            actuation_kind="Simulated",
        )
    )
    assert payload == {
        "procedure_id": str(pid),
        "reason": "beam dropped",
        "decided_by_decision_id": str(decision_id),
        "occurred_at": _NOW.isoformat(),
        "actuation_kind": "Simulated",
    }


@pytest.mark.unit
def test_to_payload_serializes_procedure_resumed_with_null_decision() -> None:
    pid = uuid4()
    payload = to_payload(
        ProcedureResumed(procedure_id=pid, re_establishment_boundary=5, occurred_at=_NOW)
    )
    assert payload == {
        "procedure_id": str(pid),
        "re_establishment_boundary": 5,
        "decided_by_decision_id": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
@pytest.mark.parametrize("decision_id", [None, uuid4()])
def test_procedure_held_round_trips(decision_id: UUID | None) -> None:
    event = ProcedureHeld(
        procedure_id=uuid4(),
        reason="investigating fault",
        decided_by_decision_id=decision_id,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("ProcedureHeld", to_payload(event)))
    assert rebuilt == event


@pytest.mark.unit
@pytest.mark.parametrize("decision_id", [None, uuid4()])
def test_procedure_resumed_round_trips(decision_id: UUID | None) -> None:
    event = ProcedureResumed(
        procedure_id=uuid4(),
        re_establishment_boundary=3,
        decided_by_decision_id=decision_id,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("ProcedureResumed", to_payload(event)))
    assert rebuilt == event


@pytest.mark.unit
def test_from_stored_held_without_decided_by_key_folds_to_none() -> None:
    """Forward-compat: a pre-supervisor stream omits decided_by_decision_id."""
    pid = uuid4()
    rebuilt = from_stored(
        _stored(
            "ProcedureHeld",
            {"procedure_id": str(pid), "reason": "pause", "occurred_at": _NOW.isoformat()},
        )
    )
    assert isinstance(rebuilt, ProcedureHeld)
    assert rebuilt.decided_by_decision_id is None


# --- SteeringDesignRecorded (design-input provenance) ---


def _steering_design_recorded(**overrides: object) -> SteeringDesignRecorded:
    fields: dict[str, object] = {
        "procedure_id": uuid4(),
        "objective": SteeringObjective(
            kind=SteeringObjectiveKind.MAXIMIZE,
            target_measurement_name="flux",
            target_value=None,
        ),
        "objective_capture_name": "flux_capture",
        "space": SteeringSpace(
            axes=(
                SteeringAxis(name="energy", lower=8000.0, upper=12000.0),
                SteeringAxis(name="mode", choices=("a", "b")),
            )
        ),
        "budget_iterations_remaining": 25,
        "budget_wall_clock_seconds_remaining": 3600.0,
        "substrate": SteeringSubstrate.BOTORCH,
        "points_per_axis": 5,
        "min_observations": 3,
        "num_restarts": 10,
        "raw_samples": 512,
        "seed": 7,
        "staged_threshold": 8,
        "spend_agent_id": uuid4(),
        "design_source": SteeringDesignSource.REQUEST,
        "occurred_at": _NOW,
        # Matches the scalars above (min_observations=3, num_restarts=10,
        # raw_samples=512, seed=7) so a test overriding one and not the
        # other cannot silently drift the two apart.
        "brain": BoTorchBrain(min_observations=3, num_restarts=10, raw_samples=512, seed=7),
    }
    fields.update(overrides)
    return SteeringDesignRecorded(**fields)  # type: ignore[arg-type]


@pytest.mark.unit
def test_event_type_name_for_steering_design_recorded() -> None:
    assert event_type_name(_steering_design_recorded()) == "SteeringDesignRecorded"


@pytest.mark.unit
def test_to_payload_serializes_steering_design_recorded_to_primitives() -> None:
    event = _steering_design_recorded()
    payload = to_payload(event)
    assert payload == {
        "procedure_id": str(event.procedure_id),
        "objective": {
            "kind": "Maximize",
            "target_measurement_name": "flux",
            "target_value": None,
        },
        "objective_capture_name": "flux_capture",
        "space": {
            "axes": [
                {"name": "energy", "lower": 8000.0, "upper": 12000.0, "choices": []},
                {"name": "mode", "lower": None, "upper": None, "choices": ["a", "b"]},
            ]
        },
        "budget_iterations_remaining": 25,
        "budget_wall_clock_seconds_remaining": 3600.0,
        "substrate": "botorch",
        "points_per_axis": 5,
        "min_observations": 3,
        "num_restarts": 10,
        "raw_samples": 512,
        "seed": 7,
        "staged_threshold": 8,
        "spend_agent_id": str(event.spend_agent_id),
        "design_source": "Request",
        "occurred_at": _NOW.isoformat(),
        "brain": {
            "min_observations": 3,
            "num_restarts": 10,
            "raw_samples": 512,
            "seed": 7,
        },
    }
    # THE ASSERTION THAT MATTERS: `objective` / `space` must stay JSON
    # primitives all the way down, or the disposition generator would
    # have classified the field opaque and record export would drop it.
    assert json.dumps(payload)


@pytest.mark.unit
def test_steering_design_recorded_round_trips() -> None:
    event = _steering_design_recorded()
    rebuilt = from_stored(_stored("SteeringDesignRecorded", to_payload(event)))
    assert rebuilt == event


@pytest.mark.unit
def test_steering_design_recorded_round_trips_with_null_budget_and_spend_agent() -> None:
    """budget_iterations_remaining / budget_wall_clock_seconds_remaining /
    spend_agent_id are the three nullable fields (exhausted budget leg,
    wall-clock-only budget, operator-issued wire request)."""
    event = _steering_design_recorded(
        budget_iterations_remaining=None,
        budget_wall_clock_seconds_remaining=None,
        spend_agent_id=None,
    )
    rebuilt = from_stored(_stored("SteeringDesignRecorded", to_payload(event)))
    assert rebuilt == event


@pytest.mark.unit
@pytest.mark.parametrize(
    ("substrate", "brain"),
    [
        (SteeringSubstrate.IN_MEMORY, InMemoryBrain()),
        (SteeringSubstrate.GRID_WALK, GridWalkBrain(points_per_axis=9)),
        (SteeringSubstrate.SOBOL, SobolBrain()),
        (
            SteeringSubstrate.BOTORCH,
            BoTorchBrain(min_observations=3, num_restarts=10, raw_samples=512, seed=7),
        ),
        (
            SteeringSubstrate.STAGED,
            StagedBrain(
                threshold=8,
                handoff_brain=BoTorchBrain(
                    min_observations=3, num_restarts=10, raw_samples=512, seed=7
                ),
            ),
        ),
        (
            SteeringSubstrate.LLM,
            LlmBrain(provider="anthropic", model="claude-sonnet-4-5", snapshot_pin=None),
        ),
        # snapshot_pin SET, not just defaulted. Hardcoding it to None in
        # `deserialize_brain` otherwise survives the whole suite, and this
        # is the field that distinguishes a pinned model from a floating
        # alias, which is the difference between a reproducible sampling
        # rule and one that can change under a deployment upgrade.
        (
            SteeringSubstrate.LLM,
            LlmBrain(
                provider="anthropic",
                model="claude-sonnet-4-5",
                snapshot_pin="claude-sonnet-4-5-20260101",
            ),
        ),
    ],
)
def test_steering_design_recorded_round_trips_every_brain(
    substrate: SteeringSubstrate, brain: SteeringBrain
) -> None:
    """One brain per substrate through to_payload/from_stored, not just BoTorch.

    Every other test on this event either uses the shared BoTorch-only
    default fixture or omits `brain` altogether; this is the only place
    all six variants -- including `llm`, which no fixture otherwise
    constructs -- actually round-trip through JSON-shaped storage.
    """
    event = _steering_design_recorded(substrate=substrate, brain=brain)
    rebuilt = from_stored(_stored("SteeringDesignRecorded", to_payload(event)))
    assert isinstance(rebuilt, SteeringDesignRecorded)
    assert rebuilt == event
    assert rebuilt.brain == brain


@pytest.mark.unit
def test_steering_design_recorded_export_drops_llm_identity_but_keeps_substrate() -> None:
    """The one substrate whose brain config exports as `{}` -- by the SAME
    rule already accepted for `objective`, not a new gap.

    `provider` / `model` / `snapshot_pin` are unconstrained strings (a
    provider set is deliberately open: `ModelRef`'s own docstring names
    `OpenAILLM` as a near-future addition), so they drop as free text
    exactly as `objective_capture_name` and `target_measurement_name`
    already do on this same event. The reader is not left with nothing:
    `substrate` is a SIBLING top-level field, `keep:enum:SteeringSubstrate`
    always, so an LLM-steered segment is still identifiable as one --
    only WHICH model is withheld, not THAT one steered. Pinned here so a
    future change that closes this gap (or accidentally widens it further)
    shows up as a deliberate diff instead of a silent one.
    """
    event = _steering_design_recorded(
        substrate=SteeringSubstrate.LLM,
        brain=LlmBrain(provider="anthropic", model="claude-sonnet-4-5", snapshot_pin=None),
    )

    exported = redact_tier1_payload(
        "SteeringDesignRecorded", to_payload(event), token_map=TokenMap()
    )

    assert exported["substrate"] == "llm"
    assert exported["brain"] == {}


@pytest.mark.unit
def test_steering_design_recorded_export_publishes_a_non_llm_brain() -> None:
    """The inverse of the llm case: a brain whose fields are all numbers
    survives export in full, keyed exactly as `to_payload` stored it."""
    event = _steering_design_recorded()  # default fixture: BoTorch

    exported = redact_tier1_payload(
        "SteeringDesignRecorded", to_payload(event), token_map=TokenMap()
    )

    assert exported["brain"] == {
        "min_observations": 3,
        "num_restarts": 10,
        "raw_samples": 512,
        "seed": 7,
    }


@pytest.mark.unit
def test_steering_design_recorded_export_publishes_the_nested_staged_brain() -> None:
    """The one arm whose disposition recurses TWO levels, through the real redactor.

    `StagedBrain.handoff_brain` is the only nested value object inside the
    merged union rule. The merge folds every arm's keys into one dict, so
    the nested arm's rule sits beside its siblings' scalar rules; if the
    redactor met it with the wrong shape it would fall through to OMITTED
    and the handoff brain would vanish while the rest of the row survived.
    """
    event = _steering_design_recorded(
        substrate=SteeringSubstrate.STAGED,
        brain=StagedBrain(
            threshold=8,
            handoff_brain=BoTorchBrain(
                min_observations=3, num_restarts=10, raw_samples=512, seed=7
            ),
        ),
    )

    exported = redact_tier1_payload(
        "SteeringDesignRecorded", to_payload(event), token_map=TokenMap()
    )

    assert exported["brain"] == {
        "threshold": 8,
        "handoff_brain": {
            "min_observations": 3,
            "num_restarts": 10,
            "raw_samples": 512,
            "seed": 7,
        },
    }


@pytest.mark.unit
def test_steering_design_recorded_disposition_classifies_every_field() -> None:
    """Pin the WHOLE table row, not a sample of it.

    `test_record_dispositions_drift.py` only proves the committed table equals
    a fresh run of the same generator, so a field silently retyped (an `int`
    tunable becoming a `str`, say) regenerates to `drop:text` and stays green
    there. Asserting the complete dict is what makes that downgrade fail, and
    `seed` is the field where it would matter most.
    """
    from cora.infrastructure.record_export._dispositions import DISPOSITIONS

    assert DISPOSITIONS["SteeringDesignRecorded"] == {
        "procedure_id": "token:uuid",
        "objective": {
            "kind": "keep:enum:SteeringObjectiveKind",
            "target_measurement_name": "drop:text",
            "target_value": "keep:number",
        },
        "objective_capture_name": "drop:text",
        "space": {
            "axes": {
                "[*]": {
                    "name": "drop:text",
                    "lower": "keep:number",
                    "upper": "keep:number",
                    "choices": "drop:opaque",
                }
            }
        },
        "budget_iterations_remaining": "keep:number",
        "budget_wall_clock_seconds_remaining": "keep:number",
        "substrate": "keep:enum:SteeringSubstrate",
        "points_per_axis": "keep:number",
        "min_observations": "keep:number",
        "num_restarts": "keep:number",
        "raw_samples": "keep:number",
        "seed": "keep:number",
        "staged_threshold": "keep:number",
        "spend_agent_id": "token:uuid",
        "design_source": "keep:enum:SteeringDesignSource",
        "occurred_at": "keep:time",
        # The MERGED rule across all six SteeringBrain variants (see
        # `SteeringBrain`'s own docstring): every arm's keys folded into
        # one dict, so `redact_tier1_payload` recurses correctly whichever
        # substrate actually stored the row. `provider` / `model` /
        # `snapshot_pin` (the `llm` arm) drop as free text by the SAME
        # rule protecting every other unconstrained string on this event
        # (`objective_capture_name`, `space.axes[*].name`); an LLM-steered
        # segment's exact model does not survive tier-1 export, ONLY its
        # `substrate` does (a sibling top-level field, always
        # `keep:enum:SteeringSubstrate`). Deliberate, precedented by
        # `target_measurement_name`'s identical gap on `objective` above,
        # not a regression: see
        # `test_steering_design_recorded_export_drops_llm_identity_but_keeps_substrate`.
        "brain": {
            "points_per_axis": "keep:number",
            "min_observations": "keep:number",
            "num_restarts": "keep:number",
            "raw_samples": "keep:number",
            "seed": "keep:number",
            "threshold": "keep:number",
            "handoff_brain": {
                "min_observations": "keep:number",
                "num_restarts": "keep:number",
                "raw_samples": "keep:number",
                "seed": "keep:number",
            },
            "provider": "drop:text",
            "model": "drop:text",
            "snapshot_pin": "drop:text",
        },
    }


@pytest.mark.unit
def test_procedure_completed_disposition_classifies_termination_reason_as_an_enum() -> None:
    """`termination_reason` must regenerate as `keep:enum:ProcedureTerminationReason`,
    not `drop:text`.

    It is typed directly on this aggregate's event, unlike `actuation_kind`
    (stranded as a raw string because `ActuationKind` lives in
    `cora.operation.ports`, which this aggregate cannot import under tach).
    A future retype to a bare `str` would regenerate to `drop:text` and the
    field would silently vanish from published records; this pin is what
    catches that, since `test_record_dispositions_drift.py` only proves the
    committed table matches a fresh run of the same generator.
    """
    from cora.infrastructure.record_export._dispositions import DISPOSITIONS

    assert DISPOSITIONS["ProcedureCompleted"] == {
        "procedure_id": "token:uuid",
        "occurred_at": "keep:time",
        "actuation_kind": "drop:text",
        "termination_reason": "keep:enum:ProcedureTerminationReason",
    }


@pytest.mark.unit
def test_procedure_completed_export_publishes_the_termination_reason() -> None:
    """Drives the real redactor, so both sides of the check are not derived
    from the same generator."""
    event = ProcedureCompleted(
        procedure_id=uuid4(),
        occurred_at=_NOW,
        termination_reason=ProcedureTerminationReason.BUDGET_ITERATIONS_EXHAUSTED,
    )
    exported = redact_tier1_payload("ProcedureCompleted", to_payload(event), token_map=TokenMap())

    assert exported["termination_reason"] == "BudgetIterationsExhausted"


@pytest.mark.unit
def test_steering_design_recorded_export_publishes_the_scalar_design() -> None:
    """What the REDACTOR emits, which is not what the table appears to promise.

    The disposition table is an input to redaction, not its output, so
    asserting the table alone leaves both sides of the check derived from the
    generator. This drives the real redactor.
    """
    event = _steering_design_recorded()
    exported = redact_tier1_payload(
        "SteeringDesignRecorded", to_payload(event), token_map=TokenMap()
    )

    assert exported["objective"]["kind"] == "Maximize"
    assert exported["substrate"] == "botorch"
    assert exported["seed"] == 7


@pytest.mark.unit
def test_steering_design_recorded_export_publishes_every_axis_bound() -> None:
    """The support survives redaction, which is what the pin is for.

    A reader cannot tell a real find from the only available option without
    the range it was drawn from, so a design that loses its axes on export
    answers nothing. Axis NAMES are `drop:text` and stay dropped; the bounds
    and the axis count are what make the support legible, and a categorical
    axis carries neither bound.
    """
    event = _steering_design_recorded()
    stored = to_payload(event)
    assert len(stored["space"]["axes"]) == 2

    exported = redact_tier1_payload("SteeringDesignRecorded", stored, token_map=TokenMap())

    assert exported["space"] == {
        "axes": [
            {"lower": 8000.0, "upper": 12000.0},
            {"lower": None, "upper": None},
        ]
    }


@pytest.mark.unit
def test_steering_design_recorded_from_stored_raises_on_any_missing_field() -> None:
    """Every required key, dropped one at a time -- except `brain`.

    The shared malformed-payload case passes `{}`, so it only ever exercises
    the first subscript and proves nothing about the fields after it. A
    `.get()` creeping into a later field would let a corrupt row deserialize
    with a plausible default, and an absent budget would become
    indistinguishable from a legitimately exhausted one.

    `brain` is deliberately excluded: it is the ONE field this event folds
    via `.get(...)`, on purpose, because a stream written before it existed
    genuinely has no such key and that is not corruption -- it is exactly
    what a pre-slice stream looks like.
    `test_steering_design_recorded_from_stored_folds_a_missing_brain_to_none`
    is the dedicated positive-case test for that fold; this test would
    otherwise assert the opposite of what `from_stored`'s own `.get(...)`
    is there to do.
    """
    payload = to_payload(_steering_design_recorded())
    for key in payload:
        if key == "brain":
            continue
        partial = {k: v for k, v in payload.items() if k != key}
        with pytest.raises(ValueError, match="Malformed SteeringDesignRecorded"):
            from_stored(_stored("SteeringDesignRecorded", partial))


@pytest.mark.unit
def test_steering_design_recorded_from_stored_folds_a_missing_brain_to_none() -> None:
    """A stream written before `brain` existed folds to `brain=None`, not a raise.

    The positive case `test_steering_design_recorded_from_stored_raises_on_any_missing_field`
    carves `brain` out of: dropping any OTHER key is corruption and must
    raise, but a pre-slice row never had this key at all, and `from_stored`
    must still fold it into a valid `Procedure` stream.
    """
    payload = to_payload(_steering_design_recorded())
    del payload["brain"]

    event = from_stored(_stored("SteeringDesignRecorded", payload))

    assert isinstance(event, SteeringDesignRecorded)
    assert event.brain is None
