"""Unit tests for the Run aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.run.aggregates.run.events import (
    DecisionDebriefRequested,
    RunAborted,
    RunCompleted,
    RunHeld,
    RunResumed,
    RunStarted,
    RunStopped,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Run",
        stream_id=stream_id or uuid4(),  # type: ignore[arg-type]
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
def test_event_type_name_returns_class_name() -> None:
    event = RunStarted(
        run_id=uuid4(),
        name="X",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "RunStarted"


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_subject_to_primitives() -> None:
    run_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    event = RunStarted(
        run_id=run_id,
        name="32-ID FlyScan",
        plan_id=plan_id,
        subject_id=subject_id,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "run_id": str(run_id),
        "name": "32-ID FlyScan",
        "plan_id": str(plan_id),
        "subject_id": str(subject_id),
        "raid": None,
        # Additive payload fields default to {} / None when not
        # supplied; legacy stored events stay forward-compat via
        # `payload.get(..., default)` in `from_stored`.
        "override_parameters": {},
        "effective_parameters": {},
        "trigger_source": None,
        # Additive payload field for `Identifier`-based anti-corruption
        # refs (proposal / btr / lab_visit / session). Defaults to []
        # when omitted; forward-compat via
        # `payload.get("external_refs", [])`.
        "external_refs": [],
        # Additive payload field for the non-blocking caution
        # snapshot (anti-pattern: ack lives on the consumption
        # event). Defaults to [] when omitted; forward-compat via
        # `payload.get("acknowledged_cautions", [])`.
        "acknowledged_cautions": [],
        # 6i-c additive payload field for optional Campaign membership
        # at start time. None when StartRun.campaign_id was not
        # provided; forward-compat via `payload.get("campaign_id")`.
        "campaign_id": None,
        # optional Decision-causation link. None when
        # StartRun.decided_by_decision_id was not provided; forward-compat
        # via `payload.get("decided_by_decision_id")`.
        "decided_by_decision_id": None,
        # sorted list of CalibrationRevision ids. Empty when
        # StartRun.pinned_calibration_ids was empty; forward-compat via
        # `payload.get("pinned_calibration_ids", [])`.
        "pinned_calibration_ids": [],
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_run_started_without_subject_as_null() -> None:
    """Dark-field / calibration runs have subject_id=None — must
    serialize as JSON null (not the string 'None')."""
    run_id = uuid4()
    plan_id = uuid4()
    event = RunStarted(
        run_id=run_id,
        name="Dark field calibration",
        plan_id=plan_id,
        subject_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["subject_id"] is None


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_raid() -> None:
    """7d retrofit: raid carries verbatim through the payload."""
    event = RunStarted(
        run_id=uuid4(),
        name="32-ID FlyScan",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        raid="https://raid.org/10.7935/cora-test-raid",
    )
    assert to_payload(event)["raid"] == "https://raid.org/10.7935/cora-test-raid"


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_6gc_parameter_fields() -> None:
    """Additive payload: override_parameters, effective_parameters,
    trigger_source carry verbatim through the payload."""
    overrides = {"energy": 12.0}
    effective = {"energy": 12.0, "exposure": 100}
    event = RunStarted(
        run_id=uuid4(),
        name="32-ID FlyScan",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        override_parameters=overrides,
        effective_parameters=effective,
        trigger_source="operator:opid:5",
    )
    payload = to_payload(event)
    assert payload["override_parameters"] == overrides
    assert payload["effective_parameters"] == effective
    assert payload["trigger_source"] == "operator:opid:5"


@pytest.mark.unit
def test_to_payload_serializes_6gc_fields_with_defaults() -> None:
    """Default empty dicts and None trigger_source serialize as `{}` /
    null (NOT omitted). Pinned because the projection's
    `bool(payload.get("override_parameters"))` test relies on the
    key being present."""
    event = RunStarted(
        run_id=uuid4(),
        name="32-ID FlyScan",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["override_parameters"] == {}
    assert payload["effective_parameters"] == {}
    assert payload["trigger_source"] is None


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_legacy_keys_as_defaults() -> None:
    """Forward-compatible load: legacy events have no
    override_parameters/effective_parameters/trigger_source keys in
    jsonb. from_stored returns the field defaults for those, keeping
    older streams replayable. Mirrors the raid forward-compat pattern."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Legacy run",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: no override_parameters, effective_parameters, or
            # trigger_source keys: this is what legacy events look like.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.override_parameters == {}
    assert event.effective_parameters == {}
    assert event.trigger_source is None


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_with_6gc_keys() -> None:
    """Post-6g-c events round-trip with parameter values intact."""
    run_id = uuid4()
    plan_id = uuid4()
    overrides = {"energy": 12.0}
    effective = {"energy": 12.0, "exposure": 100}
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Post-6g-c run",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            "override_parameters": overrides,
            "effective_parameters": effective,
            "trigger_source": "operator:opid:5",
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.override_parameters == overrides
    assert event.effective_parameters == effective
    assert event.trigger_source == "operator:opid:5"


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_raid_key_as_none() -> None:
    """Forward-compatible load: legacy events have no raid key in
    jsonb. from_stored returns raid=None for those, keeping older
    streams replayable."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Dark field calibration",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: no "raid" key — this is what legacy events look like.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.raid is None


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_with_raid_key() -> None:
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "32-ID FlyScan",
            "plan_id": str(plan_id),
            "subject_id": None,
            "raid": "https://raid.org/10.7935/cora-test-raid",
            "occurred_at": _NOW.isoformat(),
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.raid == "https://raid.org/10.7935/cora-test-raid"


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_with_subject() -> None:
    run_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "32-ID FlyScan",
            "plan_id": str(plan_id),
            "subject_id": str(subject_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunStarted(
        run_id=run_id,
        name="32-ID FlyScan",
        plan_id=plan_id,
        subject_id=subject_id,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_subject() -> None:
    """JSON null deserializes to Python None for subject_id."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Dark field",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, RunStarted)
    assert rebuilt.subject_id is None


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net for Run events."""
    original = RunStarted(
        run_id=uuid4(),
        name="X",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("RunStarted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    stored = _stored("PlanDefined", {})
    with pytest.raises(ValueError, match="Unknown RunEvent event_type"):
        from_stored(stored)


# ---------- acknowledged_cautions forward-compat + round-trip ----------


@pytest.mark.unit
def test_to_payload_serializes_acknowledged_cautions_as_list_of_dicts() -> None:
    """Each CautionAcknowledgement on the event serializes as a dict
    of primitives (caution_id + target_id are UUIDs -> str)."""
    from cora.run.aggregates.run.events import CautionAcknowledgement

    caution_id = uuid4()
    target_id = uuid4()
    event = RunStarted(
        run_id=uuid4(),
        name="Run with cautions",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        acknowledged_cautions=(
            CautionAcknowledgement(
                caution_id=caution_id,
                target_kind="Asset",
                target_id=target_id,
                category="Wear",
                severity="Warning",
                text_excerpt="bearing degraded",
                workaround_excerpt="replace within 7 days",
            ),
        ),
    )
    payload = to_payload(event)
    assert payload["acknowledged_cautions"] == [
        {
            "caution_id": str(caution_id),
            "target_kind": "Asset",
            "target_id": str(target_id),
            "category": "Wear",
            "severity": "Warning",
            "text_excerpt": "bearing degraded",
            "workaround_excerpt": "replace within 7 days",
        }
    ]


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_acknowledged_cautions_key_as_empty() -> None:
    """Forward-compat: legacy events have no acknowledged_cautions
    key. from_stored returns () for those, keeping older streams
    replayable. Mirrors the external_refs / raid forward-compat
    pattern."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Legacy run",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: no "acknowledged_cautions" key — this is what
            # legacy events look like.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.acknowledged_cautions == ()


@pytest.mark.unit
def test_acknowledged_cautions_round_trip_preserves_every_field() -> None:
    """RunStarted with acknowledged_cautions round-trips through
    to_payload + from_stored without losing any field."""
    from cora.run.aggregates.run.events import CautionAcknowledgement

    ack = CautionAcknowledgement(
        caution_id=uuid4(),
        target_kind="Procedure",
        target_id=uuid4(),
        category="Calibration",
        severity="Caution",
        text_excerpt="hexapod drift > 50 um after 30 min",
        workaround_excerpt="re-home before each scan",
    )
    original = RunStarted(
        run_id=uuid4(),
        name="Run",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        acknowledged_cautions=(ack,),
    )
    stored = _stored("RunStarted", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


# ---------- RunCompleted ----------


@pytest.mark.unit
def test_event_type_name_for_run_completed() -> None:
    event = RunCompleted(run_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "RunCompleted"


@pytest.mark.unit
def test_to_payload_serializes_run_completed_to_primitives() -> None:
    run_id = uuid4()
    event = RunCompleted(run_id=run_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "run_id": str(run_id),
        # compute-conduct provenance: None for a non-conducted complete.
        "actuation_kind": None,
        "producing_job_id": None,
        "artifact_uri": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_run_completed_with_conduct_provenance() -> None:
    run_id = uuid4()
    event = RunCompleted(
        run_id=run_id,
        actuation_kind="Simulated",
        producing_job_id="inmem-job-1",
        artifact_uri="file:///data/recon.h5",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "run_id": str(run_id),
        "actuation_kind": "Simulated",
        "producing_job_id": "inmem-job-1",
        "artifact_uri": "file:///data/recon.h5",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_run_completed() -> None:
    run_id = uuid4()
    stored = _stored(
        "RunCompleted",
        {
            "run_id": str(run_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunCompleted(run_id=run_id, occurred_at=_NOW)


@pytest.mark.unit
def test_run_completed_round_trips() -> None:
    original = RunCompleted(run_id=uuid4(), occurred_at=_NOW)
    stored = _stored("RunCompleted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_run_completed_round_trips_with_conduct_provenance() -> None:
    original = RunCompleted(
        run_id=uuid4(),
        actuation_kind="Simulated",
        producing_job_id="inmem-job-1",
        artifact_uri="file:///data/recon.h5",
        occurred_at=_NOW,
    )
    stored = _stored("RunCompleted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_rebuilds_run_completed_without_conduct_keys() -> None:
    """Pre-compute-conduct RunCompleted streams replay with the new keys
    absent, folding to None via the `.get(...)` forward-compat path."""
    run_id = uuid4()
    stored = _stored(
        "RunCompleted",
        {"run_id": str(run_id), "occurred_at": _NOW.isoformat()},
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunCompleted(run_id=run_id, occurred_at=_NOW)
    assert isinstance(rebuilt, RunCompleted)
    assert rebuilt.actuation_kind is None
    assert rebuilt.producing_job_id is None
    assert rebuilt.artifact_uri is None


# ---------- RunAborted ----------


@pytest.mark.unit
def test_event_type_name_for_run_aborted() -> None:
    event = RunAborted(run_id=uuid4(), reason="X", occurred_at=_NOW)
    assert event_type_name(event) == "RunAborted"


@pytest.mark.unit
def test_to_payload_serializes_run_aborted_to_primitives() -> None:
    run_id = uuid4()
    event = RunAborted(run_id=run_id, reason="detector overheating", occurred_at=_NOW)
    assert to_payload(event) == {
        "run_id": str(run_id),
        "reason": "detector overheating",
        # when not supplied. Forward-compat via
        # `payload.get("decided_by_decision_id")`.
        "decided_by_decision_id": None,
        # compute-conduct provenance: None for an operator abort.
        "actuation_kind": None,
        "producing_job_id": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_run_aborted() -> None:
    """Pre-Phase-1 RunAborted streams replay without the
    decided_by_decision_id key via the `.get(..., None)` forward-compat
    fold."""
    run_id = uuid4()
    stored = _stored(
        "RunAborted",
        {
            "run_id": str(run_id),
            "reason": "operator stop",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunAborted(
        run_id=run_id,
        reason="operator stop",
        occurred_at=_NOW,
    )
    assert isinstance(rebuilt, RunAborted)
    assert rebuilt.decided_by_decision_id is None
    # Pre-compute-conduct streams fold the conduct-provenance keys to None.
    assert rebuilt.actuation_kind is None
    assert rebuilt.producing_job_id is None


@pytest.mark.unit
def test_run_aborted_round_trips_with_conduct_provenance() -> None:
    original = RunAborted(
        run_id=uuid4(),
        reason="compute job failed",
        actuation_kind="Simulated",
        producing_job_id="inmem-job-1",
        occurred_at=_NOW,
    )
    stored = _stored("RunAborted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_rebuilds_run_aborted_without_decision_id_key_as_none() -> None:
    """Forward-compat: pre-Phase-1 RunAborted payloads have no
    decided_by_decision_id key. Dedicated name parallels
    `test_from_stored_rebuilds_run_started_without_decision_id_key_as_none`
    + `test_from_stored_rebuilds_run_adjusted_with_missing_decision_key_as_none`
    so each of the 3 Decision→Run linkage event sites carries its own
    forward-compat pin (cross-BC consistency review P1 #9)."""
    run_id = uuid4()
    stored = _stored(
        "RunAborted",
        {
            "run_id": str(run_id),
            "reason": "vacuum interlock fired",
            "occurred_at": _NOW.isoformat(),
            # NOTE: no decided_by_decision_id key — pre-Phase-1 shape.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunAborted)
    assert event.decided_by_decision_id is None


@pytest.mark.unit
def test_run_aborted_round_trips() -> None:
    original = RunAborted(
        run_id=uuid4(),
        reason="beam dump unscheduled",
        occurred_at=_NOW,
    )
    stored = _stored("RunAborted", to_payload(original))
    assert from_stored(stored) == original


# Decision-to-Run linkage on RunAborted


@pytest.mark.unit
def test_to_payload_serializes_run_aborted_with_decision_id() -> None:
    decision_id = uuid4()
    event = RunAborted(
        run_id=uuid4(),
        reason="agent EquipmentAbortDecision triggered",
        decided_by_decision_id=decision_id,
        occurred_at=_NOW,
    )
    assert to_payload(event)["decided_by_decision_id"] == str(decision_id)


@pytest.mark.unit
def test_run_aborted_with_decision_id_round_trips() -> None:
    original = RunAborted(
        run_id=uuid4(),
        reason="agent OperatorAbortDecision recorded",
        decided_by_decision_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("RunAborted", to_payload(original))
    assert from_stored(stored) == original


# ---------- RunHeld ----------


@pytest.mark.unit
def test_event_type_name_for_run_held() -> None:
    event = RunHeld(run_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "RunHeld"


@pytest.mark.unit
def test_to_payload_serializes_run_held_to_primitives() -> None:
    run_id = uuid4()
    event = RunHeld(run_id=run_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "run_id": str(run_id),
        "decided_by_decision_id": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_run_held() -> None:
    run_id = uuid4()
    stored = _stored(
        "RunHeld",
        {
            "run_id": str(run_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunHeld(run_id=run_id, occurred_at=_NOW)


@pytest.mark.unit
def test_run_held_round_trips() -> None:
    original = RunHeld(run_id=uuid4(), occurred_at=_NOW)
    stored = _stored("RunHeld", to_payload(original))
    assert from_stored(stored) == original


# Decision-to-Run linkage on RunHeld (RunSupervisor traceability)


@pytest.mark.unit
def test_to_payload_serializes_run_held_with_decision_id() -> None:
    decision_id = uuid4()
    event = RunHeld(
        run_id=uuid4(),
        decided_by_decision_id=decision_id,
        occurred_at=_NOW,
    )
    assert to_payload(event)["decided_by_decision_id"] == str(decision_id)


@pytest.mark.unit
def test_from_stored_rebuilds_run_held_without_decision_id_key_as_none() -> None:
    """Forward-compat: pre-supervisor RunHeld payloads have no
    decided_by_decision_id key; the `.get(..., None)` fold rebuilds None."""
    run_id = uuid4()
    stored = _stored(
        "RunHeld",
        {
            "run_id": str(run_id),
            "occurred_at": _NOW.isoformat(),
            # NOTE: no decided_by_decision_id key — pre-supervisor shape.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunHeld)
    assert event.decided_by_decision_id is None


@pytest.mark.unit
def test_run_held_with_decision_id_round_trips() -> None:
    original = RunHeld(
        run_id=uuid4(),
        decided_by_decision_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("RunHeld", to_payload(original))
    assert from_stored(stored) == original


# ---------- RunResumed ----------


@pytest.mark.unit
def test_event_type_name_for_run_resumed() -> None:
    event = RunResumed(run_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "RunResumed"


@pytest.mark.unit
def test_to_payload_serializes_run_resumed_to_primitives() -> None:
    run_id = uuid4()
    event = RunResumed(run_id=run_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "run_id": str(run_id),
        "decided_by_decision_id": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_run_resumed_with_decision_id() -> None:
    decision_id = uuid4()
    event = RunResumed(
        run_id=uuid4(),
        decided_by_decision_id=decision_id,
        occurred_at=_NOW,
    )
    assert to_payload(event)["decided_by_decision_id"] == str(decision_id)


@pytest.mark.unit
def test_from_stored_rebuilds_run_resumed() -> None:
    run_id = uuid4()
    stored = _stored(
        "RunResumed",
        {
            "run_id": str(run_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunResumed(run_id=run_id, occurred_at=_NOW)


@pytest.mark.unit
def test_from_stored_rebuilds_run_resumed_without_decision_id_key_as_none() -> None:
    """Forward-compat: pre-supervisor RunResumed payloads have no
    decided_by_decision_id key; the `.get(..., None)` fold rebuilds None."""
    run_id = uuid4()
    stored = _stored(
        "RunResumed",
        {
            "run_id": str(run_id),
            "occurred_at": _NOW.isoformat(),
            # NOTE: no decided_by_decision_id key — pre-supervisor shape.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunResumed)
    assert event.decided_by_decision_id is None


@pytest.mark.unit
def test_run_resumed_round_trips() -> None:
    original = RunResumed(run_id=uuid4(), occurred_at=_NOW)
    stored = _stored("RunResumed", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_run_resumed_with_decision_id_round_trips() -> None:
    original = RunResumed(
        run_id=uuid4(),
        decided_by_decision_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("RunResumed", to_payload(original))
    assert from_stored(stored) == original


# ---------- RunStopped ----------


@pytest.mark.unit
def test_event_type_name_for_run_stopped() -> None:
    event = RunStopped(run_id=uuid4(), reason="X", occurred_at=_NOW)
    assert event_type_name(event) == "RunStopped"


@pytest.mark.unit
def test_to_payload_serializes_run_stopped_to_primitives() -> None:
    run_id = uuid4()
    event = RunStopped(run_id=run_id, reason="hit time budget cleanly", occurred_at=_NOW)
    assert to_payload(event) == {
        "run_id": str(run_id),
        "reason": "hit time budget cleanly",
        "decided_by_decision_id": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_run_stopped() -> None:
    run_id = uuid4()
    stored = _stored(
        "RunStopped",
        {
            "run_id": str(run_id),
            "reason": "operator stop",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == RunStopped(
        run_id=run_id,
        reason="operator stop",
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_run_stopped_round_trips() -> None:
    original = RunStopped(
        run_id=uuid4(),
        reason="hit time budget cleanly",
        occurred_at=_NOW,
    )
    stored = _stored("RunStopped", to_payload(original))
    assert from_stored(stored) == original


# Decision-to-Run linkage on RunStopped (RunSupervisor traceability)


@pytest.mark.unit
def test_to_payload_serializes_run_stopped_with_decision_id() -> None:
    decision_id = uuid4()
    event = RunStopped(
        run_id=uuid4(),
        reason="agent supervisor early-stop",
        decided_by_decision_id=decision_id,
        occurred_at=_NOW,
    )
    assert to_payload(event)["decided_by_decision_id"] == str(decision_id)


@pytest.mark.unit
def test_from_stored_rebuilds_run_stopped_without_decision_id_key_as_none() -> None:
    """Forward-compat: pre-supervisor RunStopped payloads have no
    decided_by_decision_id key; the `.get(..., None)` fold rebuilds None."""
    run_id = uuid4()
    stored = _stored(
        "RunStopped",
        {
            "run_id": str(run_id),
            "reason": "hit time budget cleanly",
            "occurred_at": _NOW.isoformat(),
            # NOTE: no decided_by_decision_id key — pre-supervisor shape.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStopped)
    assert event.decided_by_decision_id is None


@pytest.mark.unit
def test_run_stopped_with_decision_id_round_trips() -> None:
    original = RunStopped(
        run_id=uuid4(),
        reason="agent supervisor early-stop",
        decided_by_decision_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("RunStopped", to_payload(original))
    assert from_stored(stored) == original


# ---------- RunObservationLogbookOpened ----------

from cora.run.aggregates.run import (  # noqa: E402
    LOGBOOK_KIND_OBSERVATION,
    OBSERVATION_LOGBOOK_SCHEMA,
)
from cora.run.aggregates.run.events import RunObservationLogbookOpened  # noqa: E402


@pytest.mark.unit
def test_event_type_name_for_run_reading_logbook_opened() -> None:
    event = RunObservationLogbookOpened(
        run_id=uuid4(),
        logbook_id=uuid4(),
        kind=LOGBOOK_KIND_OBSERVATION,
        schema=OBSERVATION_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "RunObservationLogbookOpened"


@pytest.mark.unit
def test_to_payload_serializes_run_reading_logbook_opened_to_primitives() -> None:
    """Schema flattens via LogbookSchema.to_dict for jsonb storage."""
    run_id = uuid4()
    logbook_id = uuid4()
    event = RunObservationLogbookOpened(
        run_id=run_id,
        logbook_id=logbook_id,
        kind=LOGBOOK_KIND_OBSERVATION,
        schema=OBSERVATION_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["run_id"] == str(run_id)
    assert payload["logbook_id"] == str(logbook_id)
    assert payload["kind"] == LOGBOOK_KIND_OBSERVATION
    assert payload["occurred_at"] == _NOW.isoformat()
    # Schema is a nested dict, not the LogbookSchema dataclass.
    assert isinstance(payload["schema"], dict)
    assert "fields" in payload["schema"]


@pytest.mark.unit
def test_from_stored_rebuilds_run_reading_logbook_opened() -> None:
    """Schema rebuilds from the stored dict via LogbookSchema.from_dict."""
    run_id = uuid4()
    logbook_id = uuid4()
    stored = _stored(
        "RunObservationLogbookOpened",
        {
            "run_id": str(run_id),
            "logbook_id": str(logbook_id),
            "kind": LOGBOOK_KIND_OBSERVATION,
            "schema": OBSERVATION_LOGBOOK_SCHEMA.to_dict(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, RunObservationLogbookOpened)
    assert rebuilt.run_id == run_id
    assert rebuilt.logbook_id == logbook_id
    assert rebuilt.kind == LOGBOOK_KIND_OBSERVATION
    assert rebuilt.schema.fields == OBSERVATION_LOGBOOK_SCHEMA.fields


@pytest.mark.unit
def test_run_observation_logbook_opened_round_trips() -> None:
    original = RunObservationLogbookOpened(
        run_id=uuid4(),
        logbook_id=uuid4(),
        kind=LOGBOOK_KIND_OBSERVATION,
        schema=OBSERVATION_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    stored = _stored("RunObservationLogbookOpened", to_payload(original))
    assert from_stored(stored) == original


# ---------- campaign_id additive on RunStarted + 2 new events ----------


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_campaign_id() -> None:
    """When StartRun supplied campaign_id, the event payload includes it as a
    string. Verified end-to-end via the canonical to_payload arm."""
    run_id = uuid4()
    plan_id = uuid4()
    campaign_id = uuid4()
    event = RunStarted(
        run_id=run_id,
        name="campaign-bound run",
        plan_id=plan_id,
        subject_id=None,
        occurred_at=_NOW,
        campaign_id=campaign_id,
    )
    payload = to_payload(event)
    assert payload["campaign_id"] == str(campaign_id)


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_campaign_id_as_none() -> None:
    """Forward-compat: legacy events have no campaign_id key. from_stored
    returns None for those, keeping older streams replayable. Mirrors the raid
    / external_refs / acknowledged_cautions forward-compat pattern."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Legacy run",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: no "campaign_id" key (legacy shape).
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.campaign_id is None


@pytest.mark.unit
def test_run_started_campaign_id_round_trips() -> None:
    """RunStarted with campaign_id round-trips through to_payload +
    from_stored without loss."""
    campaign_id = uuid4()
    original = RunStarted(
        run_id=uuid4(),
        name="Run",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        campaign_id=campaign_id,
    )
    stored = _stored("RunStarted", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_run_added_to_campaign_round_trips() -> None:
    """RunAddedToCampaign (post-hoc membership-assign event written by
    add_run_to_campaign) round-trips through the codec."""
    from cora.run.aggregates.run.events import RunAddedToCampaign

    original = RunAddedToCampaign(
        run_id=uuid4(),
        campaign_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("RunAddedToCampaign", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_run_removed_from_campaign_round_trips_with_reason() -> None:
    """RunRemovedFromCampaign (post-hoc membership-remove event written by
    remove_run_from_campaign) round-trips with the operator-supplied
    reason."""
    from cora.run.aggregates.run.events import RunRemovedFromCampaign

    original = RunRemovedFromCampaign(
        run_id=uuid4(),
        campaign_id=uuid4(),
        reason="moved to a follow-on study",
        occurred_at=_NOW,
    )
    stored = _stored("RunRemovedFromCampaign", to_payload(original))
    assert from_stored(stored) == original


# ---------- RunAdjusted codec ----------


@pytest.mark.unit
def test_to_payload_serializes_run_adjusted_with_decision_id() -> None:
    """6j: RunAdjusted payload carries patch, snapshot, reason,
    decided_by_decision_id (as str), occurred_at."""
    from cora.run.aggregates.run.events import RunAdjusted

    run_id = uuid4()
    decision_id = uuid4()
    actor_id = ActorId(uuid4())
    event = RunAdjusted(
        run_id=run_id,
        parameters_patch={"energy": 12.0},
        effective_parameters={"energy": 12.0, "exposure": 100},
        reason="re-center on ROI",
        adjusted_by=actor_id,
        decided_by_decision_id=decision_id,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "run_id": str(run_id),
        "parameters_patch": {"energy": 12.0},
        "effective_parameters": {"energy": 12.0, "exposure": 100},
        "reason": "re-center on ROI",
        "adjusted_by": str(actor_id),
        "decided_by_decision_id": str(decision_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_run_adjusted_without_decision_id_as_null() -> None:
    """6j: decided_by_decision_id=None serializes as JSON null
    (operator-recorded ad-hoc adjustment without a Decision citation)."""
    from cora.run.aggregates.run.events import RunAdjusted

    event = RunAdjusted(
        run_id=uuid4(),
        parameters_patch={"a": 1},
        effective_parameters={"a": 1},
        reason="x",
        adjusted_by=ActorId(uuid4()),
        occurred_at=_NOW,
    )
    assert to_payload(event)["decided_by_decision_id"] is None


@pytest.mark.unit
def test_from_stored_rebuilds_run_adjusted_with_decision_id() -> None:
    from cora.run.aggregates.run.events import RunAdjusted

    original = RunAdjusted(
        run_id=uuid4(),
        parameters_patch={"energy": 12.0},
        effective_parameters={"energy": 12.0, "exposure": 100},
        reason="agent steering iteration 5",
        adjusted_by=ActorId(uuid4()),
        decided_by_decision_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("RunAdjusted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_rebuilds_run_adjusted_without_decision_id() -> None:
    from cora.run.aggregates.run.events import RunAdjusted

    original = RunAdjusted(
        run_id=uuid4(),
        parameters_patch={"a": 1},
        effective_parameters={"a": 1},
        reason="x",
        adjusted_by=ActorId(uuid4()),
        decided_by_decision_id=None,
        occurred_at=_NOW,
    )
    stored = _stored("RunAdjusted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_rebuilds_run_adjusted_with_missing_decision_key_as_none() -> None:
    """Forward-compat: a stored RunAdjusted payload that pre-dates the
    optional `decided_by_decision_id` field (or that simply omits it)
    folds with decided_by_decision_id=None via `payload.get`."""
    from cora.run.aggregates.run.events import RunAdjusted

    run_id = uuid4()
    actor_id = uuid4()
    stored = _stored(
        "RunAdjusted",
        {
            "run_id": str(run_id),
            "parameters_patch": {"a": 1},
            "effective_parameters": {"a": 1},
            "reason": "x",
            "adjusted_by": str(actor_id),
            # NOTE: no decided_by_decision_id key
            "occurred_at": _NOW.isoformat(),
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunAdjusted)
    assert event.decided_by_decision_id is None


# ---------- Decision→Run linkage on RunStarted ----------


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_decision_id() -> None:
    """When StartRun supplied decided_by_decision_id, the event payload
    includes it as a string."""
    decision_id = uuid4()
    event = RunStarted(
        run_id=uuid4(),
        name="post-EnergyChange pivot run",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        decided_by_decision_id=decision_id,
    )
    assert to_payload(event)["decided_by_decision_id"] == str(decision_id)


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_decision_id_key_as_none() -> None:
    """Forward-compat: pre-Phase-1 events have no decided_by_decision_id
    key. from_stored returns None via `payload.get`. Mirrors the
    raid / external_refs / campaign_id forward-compat pattern."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Pre-Phase-1 run",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: no "decided_by_decision_id" key — pre-Phase-1 shape.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.decided_by_decision_id is None


@pytest.mark.unit
def test_run_started_decision_id_round_trips() -> None:
    """RunStarted with decided_by_decision_id round-trips through
    to_payload + from_stored without loss."""
    original = RunStarted(
        run_id=uuid4(),
        name="Run informed by EnergyChange decision",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        decided_by_decision_id=uuid4(),
    )
    stored = _stored("RunStarted", to_payload(original))
    assert from_stored(stored) == original


# ---------- Calibration AsShot anchor on RunStarted ----------


@pytest.mark.unit
def test_to_payload_serializes_run_started_with_pinned_calibration_ids_sorted() -> None:
    """The wire form is a list sorted lexicographically for deterministic
    byte ordering (the in-memory frozenset has no order)."""
    pin_a = UUID("01900000-0000-7000-8000-00000000ca01")
    pin_b = UUID("01900000-0000-7000-8000-00000000ca02")
    pin_c = UUID("01900000-0000-7000-8000-00000000ca03")
    event = RunStarted(
        run_id=uuid4(),
        name="Scan with pinned center + pixel-size calibrations",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        # Tuple input in scrambled order; payload must come out sorted.
        pinned_calibration_ids=(pin_c, pin_a, pin_b),
    )
    payload = to_payload(event)
    assert payload["pinned_calibration_ids"] == sorted([str(pin_a), str(pin_b), str(pin_c)])


@pytest.mark.unit
def test_from_stored_rebuilds_run_started_without_pinned_calibration_ids_key_as_empty() -> None:
    """Forward-compat: legacy RunStarted payloads have no
    pinned_calibration_ids key. from_stored returns an empty tuple via
    `payload.get(..., [])`."""
    run_id = uuid4()
    plan_id = uuid4()
    stored = _stored(
        "RunStarted",
        {
            "run_id": str(run_id),
            "name": "Legacy run",
            "plan_id": str(plan_id),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: no "pinned_calibration_ids" key — legacy shape.
        },
    )
    event = from_stored(stored)
    assert isinstance(event, RunStarted)
    assert event.pinned_calibration_ids == ()


@pytest.mark.unit
def test_run_started_pinned_calibration_ids_round_trip() -> None:
    """RunStarted with pinned_calibration_ids round-trips through to_payload +
    from_stored. The event class holds them as a tuple; equality on the
    tuple is order-sensitive but to_payload sorts before serialise."""
    pin_a = UUID("01900000-0000-7000-8000-00000000ca01")
    pin_b = UUID("01900000-0000-7000-8000-00000000ca02")
    # Use already-sorted input so round-trip equality is trivial; the
    # "decider sorts before emit" pattern is exercised in the decider
    # test_start_run_decider.py suite separately.
    original = RunStarted(
        run_id=uuid4(),
        name="Run with calibration pins",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        pinned_calibration_ids=(pin_a, pin_b),
    )
    stored = _stored("RunStarted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_decision_debrief_requested_round_trips_through_payload() -> None:
    """The lease event class round-trips through to_payload + from_stored
    so the audit trail on the Run stream survives serialization to / from
    Postgres jsonb. Per [[project-run-debriefer-lease-design]]."""
    original = DecisionDebriefRequested(
        run_id=uuid4(),
        debriefer_agent_id=uuid4(),
        terminal_event_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("DecisionDebriefRequested", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "RunStarted",
        "RunHeld",
        "RunResumed",
        "RunCompleted",
        "RunAborted",
        "RunStopped",
        "RunTruncated",
        "RunAdjusted",
        "RunObservationLogbookOpened",
        "RunAddedToCampaign",
        "RunRemovedFromCampaign",
        "DecisionDebriefRequested",
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
