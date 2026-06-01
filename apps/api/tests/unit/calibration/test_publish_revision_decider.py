"""Unit tests for the publish_revision decider (Stage 3d2 canary)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.calibration.aggregates.calibration import (
    AssertedSource,
    Calibration,
    CalibrationCannotPublishRevisionError,
    CalibrationNotFoundError,
    CalibrationRevision,
    CalibrationRevisionNotFoundError,
    CalibrationStatus,
    OutboundPermitNotActiveError,
)
from cora.calibration.features.publish_revision import (
    PublishCalibrationRevision,
    PublishRevisionEvents,
    decide,
)
from cora.federation.aggregates.permit.events import PublicationReceiptRecorded
from cora.infrastructure.ports.federation import (
    DsseStaticJwksEnvelope,
    PermitLookupResult,
)

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_PEER = "aps-2bm"
_PERMIT_ID = UUID("11111111-1111-1111-1111-111111111111")
_RECEIPT_ID = UUID("22222222-2222-2222-2222-222222222222")
_CALIBRATION_ID = UUID("33333333-3333-3333-3333-333333333333")
_REVISION_ID = UUID("44444444-4444-4444-4444-444444444444")
_PRINCIPAL_ID = UUID("55555555-5555-5555-5555-555555555555")


def _revision(
    *,
    revision_id: UUID = _REVISION_ID,
    content_hash: str | None = "a" * 64,
) -> CalibrationRevision:
    return CalibrationRevision(
        revision_id=revision_id,
        value={"value": 1.0},
        status=CalibrationStatus.VERIFIED,
        source=AssertedSource(actor_id=uuid4()),
        established_at=_NOW,
        established_by_actor_id=_PRINCIPAL_ID,
        decided_by_decision_id=None,
        supersedes_revision_id=None,
        content_hash=content_hash,
    )


def _calibration(
    *,
    revisions: tuple[CalibrationRevision, ...] | None = None,
) -> Calibration:
    return Calibration(
        id=_CALIBRATION_ID,
        target_id=uuid4(),
        quantity="rotation_center_pixels",
        operating_point={},
        description=None,
        revisions=(_revision(),) if revisions is None else revisions,
        defined_by_actor_id=_PRINCIPAL_ID,
    )


def _command(
    *,
    calibration_id: UUID = _CALIBRATION_ID,
    revision_id: UUID = _REVISION_ID,
    peer_facility_id: str = _PEER,
) -> PublishCalibrationRevision:
    return PublishCalibrationRevision(
        calibration_id=calibration_id,
        revision_id=revision_id,
        peer_facility_id=peer_facility_id,
    )


def _permit_result(*, status: str = "Active") -> PermitLookupResult:
    return PermitLookupResult(
        permit_id=_PERMIT_ID,
        peer_facility_id=_PEER,
        direction="Outbound",
        status=status,
        abi_tier_floor="Stable",
        current_version=1,
    )


def _envelope() -> DsseStaticJwksEnvelope:
    return DsseStaticJwksEnvelope(
        signing_version="cora/v1",
        payload_bytes=b"\xde\xad\xbe\xef",
    )


def _call_decide(**overrides: Any) -> PublishRevisionEvents:
    state: Calibration | None = overrides.pop("state", _calibration())
    command: PublishCalibrationRevision = overrides.pop("command", _command())
    kwargs: dict[str, Any] = {
        "permit_result": _permit_result(),
        "signature_envelope": _envelope(),
        "signature_kid": "kid-A",
        "receipt_id": _RECEIPT_ID,
        "now": _NOW,
        "published_by_actor_id": _PRINCIPAL_ID,
    }
    kwargs.update(overrides)
    return decide(state, command, **kwargs)


def test_decide_happy_path_emits_calibration_and_permit_events() -> None:
    events = _call_decide()
    assert isinstance(events, PublishRevisionEvents)

    calibration_event = events.calibration_event
    assert calibration_event.calibration_id == _CALIBRATION_ID
    assert calibration_event.revision_id == _REVISION_ID
    assert calibration_event.outbound_permit_id == _PERMIT_ID
    assert calibration_event.receipt_id == _RECEIPT_ID
    assert calibration_event.signature_envelope_kind == "dsse_static_jwks"
    assert calibration_event.signing_version == "cora/v1"
    assert calibration_event.signature_bytes_hex == "deadbeef"
    assert calibration_event.signature_kid == "kid-A"
    assert calibration_event.published_by_actor_id == _PRINCIPAL_ID
    assert calibration_event.publication_status == "Live"
    assert calibration_event.published_at == _NOW
    assert calibration_event.occurred_at == _NOW

    permit_event = events.permit_event
    assert isinstance(permit_event, PublicationReceiptRecorded)
    assert permit_event.permit_id == _PERMIT_ID
    assert permit_event.content_hash == "a" * 64
    assert permit_event.home_stream_type == "Calibration"
    assert permit_event.home_stream_id == _CALIBRATION_ID
    assert permit_event.home_artifact_id == _REVISION_ID
    assert permit_event.receipt_id == _RECEIPT_ID
    assert permit_event.recorded_at == _NOW


def test_decide_calibration_state_none_raises_calibration_not_found() -> None:
    with pytest.raises(CalibrationNotFoundError) as exc_info:
        _call_decide(state=None)
    assert exc_info.value.calibration_id == _CALIBRATION_ID


def test_decide_revision_not_on_aggregate_raises_revision_not_found() -> None:
    other_revision_id = UUID("99999999-9999-9999-9999-999999999999")
    with pytest.raises(CalibrationRevisionNotFoundError) as exc_info:
        _call_decide(command=_command(revision_id=other_revision_id))
    assert exc_info.value.calibration_id == _CALIBRATION_ID
    assert exc_info.value.revision_id == other_revision_id


def test_decide_legacy_revision_without_content_hash_raises_missing_content_hash() -> None:
    legacy_revision = _revision(content_hash=None)
    legacy_calibration = _calibration(revisions=(legacy_revision,))
    with pytest.raises(CalibrationCannotPublishRevisionError) as exc_info:
        _call_decide(state=legacy_calibration)
    assert exc_info.value.calibration_id == _CALIBRATION_ID
    assert exc_info.value.revision_id == _REVISION_ID


def test_decide_no_permit_lookup_result_raises_outbound_permit_not_active() -> None:
    with pytest.raises(OutboundPermitNotActiveError) as exc_info:
        _call_decide(permit_result=None)
    assert exc_info.value.peer_facility_id == _PEER
    assert exc_info.value.artifact_kind == "CalibrationRevision"
    assert exc_info.value.status == "<unresolved>"


def test_decide_suspended_permit_raises_outbound_permit_not_active() -> None:
    with pytest.raises(OutboundPermitNotActiveError) as exc_info:
        _call_decide(permit_result=_permit_result(status="Suspended"))
    assert exc_info.value.status == "Suspended"


def test_decide_revoked_permit_raises_outbound_permit_not_active() -> None:
    with pytest.raises(OutboundPermitNotActiveError):
        _call_decide(permit_result=_permit_result(status="Revoked"))


def test_decide_defined_permit_raises_outbound_permit_not_active() -> None:
    with pytest.raises(OutboundPermitNotActiveError):
        _call_decide(permit_result=_permit_result(status="Defined"))


def test_decide_picks_target_revision_when_aggregate_has_multiple() -> None:
    target_revision_id = UUID("66666666-6666-6666-6666-666666666666")
    other_revision_id = UUID("77777777-7777-7777-7777-777777777777")
    revisions = (
        _revision(revision_id=other_revision_id, content_hash="b" * 64),
        _revision(revision_id=target_revision_id, content_hash="c" * 64),
    )
    calibration = _calibration(revisions=revisions)
    events = _call_decide(
        state=calibration,
        command=_command(revision_id=target_revision_id),
    )
    assert events.calibration_event.revision_id == target_revision_id
    assert events.permit_event.content_hash == "c" * 64


def test_decide_calibration_event_signature_bytes_hex_round_trips_via_hex() -> None:
    envelope = DsseStaticJwksEnvelope(signing_version="cora/v1", payload_bytes=b"\x00\x01\x02\xff")
    events = _call_decide(signature_envelope=envelope)
    assert events.calibration_event.signature_bytes_hex == "000102ff"
    assert bytes.fromhex(events.calibration_event.signature_bytes_hex) == envelope.payload_bytes
