"""ClearanceEvent serialization round-trips: to_payload + from_stored + helpers."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.safety.aggregates.clearance import (
    AssetBinding,
    ClearanceActivated,
    ClearanceApproved,
    ClearanceExpired,
    ClearanceRegistered,
    ClearanceRejected,
    ClearanceReviewStarted,
    ClearanceReviewStepAppended,
    ClearanceSubmitted,
    ClearanceSuperseded,
    ExternalRefBinding,
    HazardDeclaration,
    ProcedureBinding,
    RunBinding,
    SubjectBinding,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.safety.aggregates.clearance.events import (
    deserialize_binding,
    deserialize_classification,
    deserialize_declaration,
    serialize_binding,
    serialize_classification,
    serialize_declaration,
)
from cora.safety.aggregates.clearance.hazard_classification import (
    GHSPictogram,
    NFPA704Rating,
    RiskBand,
    SchemeCode,
)
from cora.shared.identifier import Identifier
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_CLEARANCE_ID = UUID("01900000-0000-7000-8000-000000011001")


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Clearance",
        stream_id=_CLEARANCE_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- serialize_binding / deserialize_binding ----------


@pytest.mark.unit
def test_serialize_binding_subject_round_trip() -> None:
    sid = uuid4()
    original = SubjectBinding(subject_id=sid)
    encoded = serialize_binding(original)
    assert encoded == {"kind": "Subject", "id": str(sid)}
    assert deserialize_binding(encoded) == original


@pytest.mark.unit
def test_serialize_binding_asset_round_trip() -> None:
    aid = uuid4()
    original = AssetBinding(asset_id=aid)
    encoded = serialize_binding(original)
    assert encoded == {"kind": "Asset", "id": str(aid)}
    assert deserialize_binding(encoded) == original


@pytest.mark.unit
def test_serialize_binding_run_round_trip() -> None:
    rid = uuid4()
    original = RunBinding(run_id=rid)
    encoded = serialize_binding(original)
    assert encoded == {"kind": "Run", "id": str(rid)}
    assert deserialize_binding(encoded) == original


@pytest.mark.unit
def test_serialize_binding_procedure_round_trip() -> None:
    pid = uuid4()
    original = ProcedureBinding(procedure_id=pid)
    encoded = serialize_binding(original)
    assert encoded == {"kind": "Procedure", "id": str(pid)}
    assert deserialize_binding(encoded) == original


@pytest.mark.unit
def test_serialize_binding_external_round_trip() -> None:
    original = ExternalRefBinding(ref=Identifier(scheme="proposal", value="GUP-12345"))
    encoded = serialize_binding(original)
    assert encoded == {"kind": "External", "scheme": "proposal", "value": "GUP-12345"}
    assert deserialize_binding(encoded) == original


@pytest.mark.unit
def test_deserialize_binding_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown ClearanceBinding kind"):
        deserialize_binding({"kind": "Mystery", "id": "x"})


@pytest.mark.unit
def test_deserialize_binding_rejects_missing_id_field() -> None:
    """Missing inner field is surfaced as ValueError (not KeyError) so callers
    see a single failure mode for contaminated payloads."""
    with pytest.raises(ValueError, match="Malformed ClearanceBinding"):
        deserialize_binding({"kind": "Subject"})


@pytest.mark.unit
def test_deserialize_binding_rejects_missing_kind_field() -> None:
    with pytest.raises(ValueError, match="Malformed ClearanceBinding"):
        deserialize_binding({"id": "x"})


@pytest.mark.unit
def test_deserialize_binding_rejects_non_uuid_id() -> None:
    """UUID() raises ValueError natively; verify the wrap layer still surfaces
    a ValueError consistent with the other malformed-payload paths."""
    with pytest.raises(ValueError):
        deserialize_binding({"kind": "Subject", "id": "not-a-uuid"})


@pytest.mark.unit
def test_deserialize_binding_rejects_external_missing_scheme() -> None:
    with pytest.raises(ValueError, match="Malformed ClearanceBinding"):
        deserialize_binding({"kind": "External", "value": "GUP-1"})


# ---------- serialize_classification / deserialize_classification ----------


@pytest.mark.unit
def test_serialize_classification_nfpa704_round_trip() -> None:
    original = NFPA704Rating(health=2, flammability=1, instability=0, special="OX")
    encoded = serialize_classification(original)
    assert encoded == {
        "kind": "NFPA704",
        "health": 2,
        "flammability": 1,
        "instability": 0,
        "special": "OX",
    }
    assert deserialize_classification(encoded) == original


@pytest.mark.unit
def test_serialize_classification_risk_band_round_trip() -> None:
    encoded = serialize_classification(RiskBand.YELLOW)
    assert encoded == {"kind": "RiskBand", "band": "Yellow"}
    assert deserialize_classification(encoded) == RiskBand.YELLOW


@pytest.mark.unit
def test_serialize_classification_ghs_round_trip() -> None:
    original = GHSPictogram(code="GHS06", statement_codes=frozenset({"H300", "H311"}))
    encoded = serialize_classification(original)
    assert encoded["kind"] == "GHS"
    assert encoded["code"] == "GHS06"
    assert encoded["statement_codes"] == ["H300", "H311"]  # sorted
    assert deserialize_classification(encoded) == original


@pytest.mark.unit
def test_serialize_classification_scheme_round_trip() -> None:
    original = SchemeCode(scheme="ANSI_Z136", code="Class_4", severity_label="extreme")
    encoded = serialize_classification(original)
    assert encoded == {
        "kind": "Scheme",
        "scheme": "ANSI_Z136",
        "code": "Class_4",
        "severity_label": "extreme",
    }
    assert deserialize_classification(encoded) == original


@pytest.mark.unit
def test_deserialize_classification_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown HazardClassification kind"):
        deserialize_classification({"kind": "Mystery"})


@pytest.mark.unit
def test_deserialize_classification_rejects_missing_inner_field() -> None:
    """Missing inner NFPA704 health/flammability/instability surfaces as ValueError."""
    with pytest.raises(ValueError, match="Malformed HazardClassification"):
        deserialize_classification({"kind": "NFPA704", "health": 1, "flammability": 0})


@pytest.mark.unit
def test_deserialize_classification_rejects_missing_kind_field() -> None:
    with pytest.raises(ValueError, match="Malformed HazardClassification"):
        deserialize_classification({"health": 1})


# ---------- serialize_declaration / deserialize_declaration ----------


@pytest.mark.unit
def test_serialize_declaration_round_trip() -> None:
    sid = uuid4()
    original = HazardDeclaration(
        target=SubjectBinding(subject_id=sid),
        classifications=frozenset(
            {NFPA704Rating(health=2, flammability=1, instability=0), RiskBand.YELLOW}
        ),
        mitigations=frozenset({"training:hazcom-2026", "ppe:nitrile_gloves"}),
        notes="Sample notes",
    )
    encoded = serialize_declaration(original)
    rebuilt = deserialize_declaration(encoded)
    assert rebuilt.target == original.target
    assert rebuilt.classifications == original.classifications
    assert rebuilt.mitigations == original.mitigations
    assert rebuilt.notes == original.notes


# ---------- ClearanceRegistered ----------


@pytest.mark.unit
def test_clearance_registered_event_type_name() -> None:
    event = ClearanceRegistered(
        clearance_id=_CLEARANCE_ID,
        kind="ESAF",
        facility_asset_id=uuid4(),
        title="t",
        bindings=({"kind": "Run", "id": str(uuid4())},),
        declarations=(),
        risk_band=None,
        external_id=None,
        valid_from=None,
        valid_until=None,
        parent_id=None,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ClearanceRegistered"


@pytest.mark.unit
def test_clearance_registered_to_payload_round_trip() -> None:
    rid = uuid4()
    sid = uuid4()
    original = ClearanceRegistered(
        clearance_id=_CLEARANCE_ID,
        kind="ESAF",
        facility_asset_id=uuid4(),
        title="Pilot ESAF for 2-BM",
        bindings=(
            {"kind": "Run", "id": str(rid)},
            {"kind": "Subject", "id": str(sid)},
            {"kind": "External", "scheme": "proposal", "value": "GUP-12345"},
        ),
        declarations=(
            {
                "target": {"kind": "Subject", "id": str(sid)},
                "classifications": [
                    {"kind": "RiskBand", "band": "Yellow"},
                ],
                "mitigations": ["ppe:gloves"],
                "notes": "test",
            },
        ),
        risk_band="Yellow",
        external_id="ESAF-99999",
        valid_from=_NOW,
        valid_until=None,
        parent_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    rebuilt = from_stored(_stored("ClearanceRegistered", payload))
    assert rebuilt == original


@pytest.mark.unit
def test_from_stored_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown ClearanceEvent event_type"):
        from_stored(_stored("ImaginaryEvent", {}))


@pytest.mark.unit
def test_clearance_registered_round_trip_handles_optional_datetimes() -> None:
    """valid_from / valid_until / parent_id None values survive round-trip."""
    parent = uuid4()
    original = ClearanceRegistered(
        clearance_id=_CLEARANCE_ID,
        kind="DOOR",
        facility_asset_id=uuid4(),
        title="t",
        bindings=({"kind": "External", "scheme": "btr", "value": "BTR-1"},),
        declarations=(),
        risk_band="Green",
        external_id=None,
        valid_from=None,
        valid_until=None,
        parent_id=parent,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("ClearanceRegistered", to_payload(original)))
    assert isinstance(rebuilt, ClearanceRegistered)
    assert rebuilt.parent_id == parent
    assert rebuilt.valid_from is None
    assert rebuilt.valid_until is None


# ---------- 6 FSM-closure event round-trips (11a-b) ----------
#
# These pin the wire shape of each FSM-closure event. Two of them
# (ClearanceApproved, ClearanceRejected) had their payload shape just
# changed: the approving/rejecting actor's identity moved from the
# payload to the envelope (StoredEvent.principal_id) per cross-BC
# precedent. The negative assertions below pin the field's absence so
# a regression that re-adds it is caught immediately.


@pytest.mark.unit
def test_clearance_submitted_round_trip() -> None:
    original = ClearanceSubmitted(clearance_id=_CLEARANCE_ID, occurred_at=_NOW)
    payload = to_payload(original)
    assert payload == {"clearance_id": str(_CLEARANCE_ID), "occurred_at": _NOW.isoformat()}
    assert from_stored(_stored("ClearanceSubmitted", payload)) == original
    assert event_type_name(original) == "ClearanceSubmitted"


@pytest.mark.unit
def test_clearance_review_started_round_trip() -> None:
    original = ClearanceReviewStarted(
        clearance_id=_CLEARANCE_ID,
        first_reviewer_role="BeamlineScientist",
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    assert payload["first_reviewer_role"] == "BeamlineScientist"
    assert from_stored(_stored("ClearanceReviewStarted", payload)) == original
    assert event_type_name(original) == "ClearanceReviewStarted"


@pytest.mark.unit
def test_clearance_review_step_appended_round_trip() -> None:
    decided_by = ActorId(uuid4())
    original = ClearanceReviewStepAppended(
        clearance_id=_CLEARANCE_ID,
        step_index=2,
        role="ESH",
        decided_by=decided_by,
        decision="Approved",
        decided_at=_NOW,
        notes="LGTM",
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    assert payload["step_index"] == 2
    assert payload["decided_by"] == str(decided_by)
    assert payload["decision"] == "Approved"
    assert payload["decided_at"] == _NOW.isoformat()
    assert from_stored(_stored("ClearanceReviewStepAppended", payload)) == original


@pytest.mark.unit
def test_clearance_review_step_appended_round_trip_handles_none_notes() -> None:
    original = ClearanceReviewStepAppended(
        clearance_id=_CLEARANCE_ID,
        step_index=0,
        role="LocalContact",
        decided_by=ActorId(uuid4()),
        decision="RequestedChanges",
        decided_at=_NOW,
        notes=None,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("ClearanceReviewStepAppended", to_payload(original)))
    assert isinstance(rebuilt, ClearanceReviewStepAppended)
    assert rebuilt.notes is None


@pytest.mark.unit
def test_clearance_approved_round_trip_drops_approving_actor_id_from_payload() -> None:
    """Approving actor lives on `StoredEvent.principal_id`, NOT the payload.

    Pins the payload-shape change: `approving_actor_id` was removed from
    `ClearanceApproved` per cross-BC `RunAborted` / `ProcedureAborted`
    precedent. A regression that re-adds the key would land here.
    """
    original = ClearanceApproved(
        clearance_id=_CLEARANCE_ID,
        valid_from=None,
        valid_until=None,
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    assert "approving_actor_id" not in payload
    assert payload == {
        "clearance_id": str(_CLEARANCE_ID),
        "valid_from": None,
        "valid_until": None,
        "occurred_at": _NOW.isoformat(),
    }
    assert from_stored(_stored("ClearanceApproved", payload)) == original
    assert event_type_name(original) == "ClearanceApproved"


@pytest.mark.unit
def test_clearance_approved_round_trip_carries_validity_window() -> None:
    valid_from = datetime(2026, 6, 1, tzinfo=UTC)
    valid_until = datetime(2026, 9, 1, tzinfo=UTC)
    original = ClearanceApproved(
        clearance_id=_CLEARANCE_ID,
        valid_from=valid_from,
        valid_until=valid_until,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("ClearanceApproved", to_payload(original)))
    assert isinstance(rebuilt, ClearanceApproved)
    assert rebuilt.valid_from == valid_from
    assert rebuilt.valid_until == valid_until


@pytest.mark.unit
def test_clearance_rejected_round_trip_drops_rejecting_actor_id_from_payload() -> None:
    """Rejecting actor lives on `StoredEvent.principal_id`, NOT the payload.

    Pins the payload-shape change: `rejecting_actor_id` was removed from
    `ClearanceRejected` per the same precedent as ClearanceApproved.
    """
    original = ClearanceRejected(
        clearance_id=_CLEARANCE_ID,
        reason="ESRB found insufficient PPE specification",
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    assert "rejecting_actor_id" not in payload
    assert payload == {
        "clearance_id": str(_CLEARANCE_ID),
        "reason": "ESRB found insufficient PPE specification",
        "occurred_at": _NOW.isoformat(),
    }
    assert from_stored(_stored("ClearanceRejected", payload)) == original
    assert event_type_name(original) == "ClearanceRejected"


@pytest.mark.unit
def test_clearance_activated_round_trip() -> None:
    original = ClearanceActivated(clearance_id=_CLEARANCE_ID, occurred_at=_NOW)
    payload = to_payload(original)
    assert payload == {"clearance_id": str(_CLEARANCE_ID), "occurred_at": _NOW.isoformat()}
    assert from_stored(_stored("ClearanceActivated", payload)) == original
    assert event_type_name(original) == "ClearanceActivated"


@pytest.mark.unit
def test_clearance_expired_round_trip() -> None:
    """Pin to_payload + from_stored for ClearanceExpired (the terminal-
    no-successor event); reason is required (Active -> Expired needs an
    audit trail explaining why)."""
    original = ClearanceExpired(
        clearance_id=_CLEARANCE_ID,
        reason="valid_until elapsed before renewal arrived",
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    assert payload == {
        "clearance_id": str(_CLEARANCE_ID),
        "reason": "valid_until elapsed before renewal arrived",
        "occurred_at": _NOW.isoformat(),
    }
    assert from_stored(_stored("ClearanceExpired", payload)) == original
    assert event_type_name(original) == "ClearanceExpired"


@pytest.mark.unit
def test_clearance_superseded_round_trip() -> None:
    """Pin the parent-clearance pointer round-trip; `by_clearance_id` is
    the new Active Clearance taking over."""
    by_id = UUID("01900000-0000-7000-8000-000000011002")
    original = ClearanceSuperseded(
        clearance_id=_CLEARANCE_ID,
        by_clearance_id=by_id,
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    assert payload == {
        "clearance_id": str(_CLEARANCE_ID),
        "by_clearance_id": str(by_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert from_stored(_stored("ClearanceSuperseded", payload)) == original
    assert event_type_name(original) == "ClearanceSuperseded"


# ---------------------------------------------------------------------------
# Malformed-payload defensive arm in the HazardDeclaration helper
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_deserialize_declaration_raises_on_malformed_payload() -> None:
    """`deserialize_declaration` is the helper for the embedded
    `HazardDeclaration` value-object inside `ClearanceRegistered.declarations`.
    Wraps KeyError/TypeError/AttributeError to a tagged ValueError so a
    contaminated stream fails loud at evolver time rather than bubbling
    a raw error from `deserialize_binding`. Safety's `from_stored` itself
    does NOT wrap KeyError (one of the two BC styles in CORA; agent and
    caution use the per-event try/except wrap; safety lets raw KeyError
    surface). This helper is the only defensive raise on the safety side."""
    with pytest.raises(ValueError, match="Malformed HazardDeclaration payload"):
        deserialize_declaration({})  # missing required `target` field
