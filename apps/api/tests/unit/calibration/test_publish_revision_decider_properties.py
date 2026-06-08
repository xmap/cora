"""Property tests for the publish_revision decider (Calibration BC).

Cross-BC federation decider. Pure shape:

    decide(state, command, *, permit_result, signature_envelope,
           signature_kid, receipt_id, now, published_by)
        -> PublishRevisionEvents

Universal claims pinned here:

  - Genesis-as-error: state=None always raises CalibrationNotFoundError.
  - Revision-presence guard: unknown revision_id always raises
    CalibrationRevisionNotFoundError, taking precedence over the
    permit check.
  - Legacy-revision guard: revision.content_hash=None always raises
    CalibrationCannotPublishRevisionError.
  - Permit-active guard: any non-Active permit (or permit_result=None)
    always raises OutboundPermitNotActiveError.
  - Event-shape stability: when all four guards pass, the two-event
    pair carries every injected field verbatim and shares receipt_id
    across streams.
  - Purity: identical inputs yield identical event pairs.

The decider is acknowledged NOT idempotent; handler-side wraps with
an Idempotency-Key. Re-issue de-duplication is not asserted here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from datetime import datetime

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
    decide,
)
from cora.infrastructure.ports.federation import (
    DsseStaticJwksEnvelope,
    PermitLookupResult,
)
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH, FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

_HEX_CHAR = st.sampled_from("0123456789abcdef")
_CONTENT_HASH = st.lists(_HEX_CHAR, min_size=64, max_size=64).map("".join)
# Constrain to valid FacilityCode shape so the same value can flow into
# both the command's bare-string peer_facility_id and the typed
# PermitLookupResult.peer_facility_id (FacilityCode) post Slice 3 of
# project_structural_scope_design.
_FACILITY_CODE_CHAR = st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-")
_PEER_FACILITY_ID = st.lists(
    _FACILITY_CODE_CHAR, min_size=1, max_size=FACILITY_CODE_MAX_LENGTH
).map("".join)
_SIGNATURE_KID = printable_ascii_text(min_size=1, max_size=128)
_SIGNING_VERSION = st.sampled_from(["cora/v1"])
_PAYLOAD_BYTES = st.binary(min_size=1, max_size=512)
_PERMIT_NON_ACTIVE_STATUS = st.sampled_from(["Defined", "Suspended", "Revoked"])
_PERMIT_ANY_STATUS = st.sampled_from(["Defined", "Active", "Suspended", "Revoked"])


def _revision(
    *,
    revision_id: UUID,
    content_hash: str | None,
    established_at: datetime,
    established_by: ActorId,
) -> CalibrationRevision:
    return CalibrationRevision(
        revision_id=revision_id,
        value={"value": 1.0},
        status=CalibrationStatus.VERIFIED,
        source=AssertedSource(asserted_by=ActorId(uuid4())),
        established_at=established_at,
        established_by=established_by,
        decided_by_decision_id=None,
        supersedes_revision_id=None,
        content_hash=content_hash,
    )


def _calibration(
    *,
    calibration_id: UUID,
    revisions: tuple[CalibrationRevision, ...],
    actor_id: ActorId,
    defined_at: datetime,
) -> Calibration:
    return Calibration(
        id=calibration_id,
        target_id=uuid4(),
        quantity="rotation_center_pixels",
        operating_point={},
        description=None,
        revisions=revisions,
        defined_at=defined_at,
        defined_by=actor_id,
    )


def _envelope(payload_bytes: bytes, signing_version: str) -> DsseStaticJwksEnvelope:
    return DsseStaticJwksEnvelope(
        signing_version=signing_version,
        payload_bytes=payload_bytes,
    )


def _permit(*, permit_id: UUID, peer_facility_id: str, status: str) -> PermitLookupResult:
    return PermitLookupResult(
        permit_id=permit_id,
        peer_facility_id=FacilityCode(peer_facility_id),
        direction="Outbound",
        status=status,
        abi_tier_floor="Stable",
        current_version=1,
    )


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    revision_id=st.uuids(),
    peer_facility_id=_PEER_FACILITY_ID,
    receipt_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decide_with_no_calibration_always_raises_not_found(
    calibration_id: UUID,
    revision_id: UUID,
    peer_facility_id: str,
    receipt_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state=None always raises CalibrationNotFoundError; the genesis
    guard is unconditional and runs before any permit or revision lookup."""
    command = PublishCalibrationRevision(
        calibration_id=calibration_id,
        revision_id=revision_id,
        peer_facility_id=peer_facility_id,
    )
    with pytest.raises(CalibrationNotFoundError):
        decide(
            None,
            command,
            permit_result=_permit(
                permit_id=uuid4(), peer_facility_id=peer_facility_id, status="Active"
            ),
            signature_envelope=_envelope(b"\xde\xad", "cora/v1"),
            signature_kid="kid",
            receipt_id=receipt_id,
            now=now,
            published_by=actor_id,
        )


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    known_revision_id=st.uuids(),
    queried_revision_id=st.uuids(),
    permit_status=_PERMIT_ANY_STATUS,
    content_hash=_CONTENT_HASH,
    peer_facility_id=_PEER_FACILITY_ID,
    receipt_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decide_with_unknown_revision_always_raises_revision_not_found(
    calibration_id: UUID,
    known_revision_id: UUID,
    queried_revision_id: UUID,
    permit_status: str,
    content_hash: str,
    peer_facility_id: str,
    receipt_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Unknown revision_id raises CalibrationRevisionNotFoundError regardless
    of permit status; pins revision-guard precedence over permit-guard."""
    assume(queried_revision_id != known_revision_id)
    state = _calibration(
        calibration_id=calibration_id,
        revisions=(
            _revision(
                revision_id=known_revision_id,
                content_hash=content_hash,
                established_at=now,
                established_by=ActorId(actor_id),
            ),
        ),
        actor_id=ActorId(actor_id),
        defined_at=now,
    )
    command = PublishCalibrationRevision(
        calibration_id=calibration_id,
        revision_id=queried_revision_id,
        peer_facility_id=peer_facility_id,
    )
    with pytest.raises(CalibrationRevisionNotFoundError):
        decide(
            state,
            command,
            permit_result=_permit(
                permit_id=uuid4(), peer_facility_id=peer_facility_id, status=permit_status
            ),
            signature_envelope=_envelope(b"\xde\xad", "cora/v1"),
            signature_kid="kid",
            receipt_id=receipt_id,
            now=now,
            published_by=actor_id,
        )


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    revision_id=st.uuids(),
    permit_status=_PERMIT_ANY_STATUS,
    peer_facility_id=_PEER_FACILITY_ID,
    receipt_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decide_with_legacy_revision_always_raises_cannot_publish(
    calibration_id: UUID,
    revision_id: UUID,
    permit_status: str,
    peer_facility_id: str,
    receipt_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """A revision with content_hash=None (pre-rollout legacy) always raises
    CalibrationCannotPublishRevisionError, independent of permit status."""
    state = _calibration(
        calibration_id=calibration_id,
        revisions=(
            _revision(
                revision_id=revision_id,
                content_hash=None,
                established_at=now,
                established_by=ActorId(actor_id),
            ),
        ),
        actor_id=ActorId(actor_id),
        defined_at=now,
    )
    command = PublishCalibrationRevision(
        calibration_id=calibration_id,
        revision_id=revision_id,
        peer_facility_id=peer_facility_id,
    )
    with pytest.raises(CalibrationCannotPublishRevisionError):
        decide(
            state,
            command,
            permit_result=_permit(
                permit_id=uuid4(), peer_facility_id=peer_facility_id, status=permit_status
            ),
            signature_envelope=_envelope(b"\xde\xad", "cora/v1"),
            signature_kid="kid",
            receipt_id=receipt_id,
            now=now,
            published_by=actor_id,
        )


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    revision_id=st.uuids(),
    content_hash=_CONTENT_HASH,
    permit_status=_PERMIT_NON_ACTIVE_STATUS,
    peer_facility_id=_PEER_FACILITY_ID,
    receipt_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decide_with_inactive_permit_always_raises_permit_not_active(
    calibration_id: UUID,
    revision_id: UUID,
    content_hash: str,
    permit_status: str,
    peer_facility_id: str,
    receipt_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Any permit in Defined / Suspended / Revoked always raises
    OutboundPermitNotActiveError; Active-only authorization."""
    state = _calibration(
        calibration_id=calibration_id,
        revisions=(
            _revision(
                revision_id=revision_id,
                content_hash=content_hash,
                established_at=now,
                established_by=ActorId(actor_id),
            ),
        ),
        actor_id=ActorId(actor_id),
        defined_at=now,
    )
    command = PublishCalibrationRevision(
        calibration_id=calibration_id,
        revision_id=revision_id,
        peer_facility_id=peer_facility_id,
    )
    with pytest.raises(OutboundPermitNotActiveError):
        decide(
            state,
            command,
            permit_result=_permit(
                permit_id=uuid4(), peer_facility_id=peer_facility_id, status=permit_status
            ),
            signature_envelope=_envelope(b"\xde\xad", "cora/v1"),
            signature_kid="kid",
            receipt_id=receipt_id,
            now=now,
            published_by=actor_id,
        )


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    revision_id=st.uuids(),
    content_hash=_CONTENT_HASH,
    peer_facility_id=_PEER_FACILITY_ID,
    receipt_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decide_with_missing_permit_always_raises_permit_not_active(
    calibration_id: UUID,
    revision_id: UUID,
    content_hash: str,
    peer_facility_id: str,
    receipt_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """permit_result=None (no matching permit found) always raises
    OutboundPermitNotActiveError; pins the None branch as equivalent
    to non-Active."""
    state = _calibration(
        calibration_id=calibration_id,
        revisions=(
            _revision(
                revision_id=revision_id,
                content_hash=content_hash,
                established_at=now,
                established_by=ActorId(actor_id),
            ),
        ),
        actor_id=ActorId(actor_id),
        defined_at=now,
    )
    command = PublishCalibrationRevision(
        calibration_id=calibration_id,
        revision_id=revision_id,
        peer_facility_id=peer_facility_id,
    )
    with pytest.raises(OutboundPermitNotActiveError):
        decide(
            state,
            command,
            permit_result=None,
            signature_envelope=_envelope(b"\xde\xad", "cora/v1"),
            signature_kid="kid",
            receipt_id=receipt_id,
            now=now,
            published_by=actor_id,
        )


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    revision_id=st.uuids(),
    permit_id=st.uuids(),
    content_hash=_CONTENT_HASH,
    peer_facility_id=_PEER_FACILITY_ID,
    receipt_id=st.uuids(),
    signing_version=_SIGNING_VERSION,
    payload_bytes=_PAYLOAD_BYTES,
    signature_kid=_SIGNATURE_KID,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decide_happy_path_emits_event_pair_with_injected_fields(
    calibration_id: UUID,
    revision_id: UUID,
    permit_id: UUID,
    content_hash: str,
    peer_facility_id: str,
    receipt_id: UUID,
    signing_version: str,
    payload_bytes: bytes,
    signature_kid: str,
    now: datetime,
    actor_id: UUID,
) -> None:
    """All guards pass: the cross-BC event pair carries injected fields
    verbatim. receipt_id is shared across both streams; content_hash on
    the permit event mirrors the revision; signature_bytes_hex is the
    hex of the envelope payload bytes."""
    envelope = _envelope(payload_bytes, signing_version)
    permit = _permit(permit_id=permit_id, peer_facility_id=peer_facility_id, status="Active")
    state = _calibration(
        calibration_id=calibration_id,
        revisions=(
            _revision(
                revision_id=revision_id,
                content_hash=content_hash,
                established_at=now,
                established_by=ActorId(actor_id),
            ),
        ),
        actor_id=ActorId(actor_id),
        defined_at=now,
    )
    command = PublishCalibrationRevision(
        calibration_id=calibration_id,
        revision_id=revision_id,
        peer_facility_id=peer_facility_id,
    )
    result = decide(
        state,
        command,
        permit_result=permit,
        signature_envelope=envelope,
        signature_kid=signature_kid,
        receipt_id=receipt_id,
        now=now,
        published_by=actor_id,
    )

    pub = result.calibration_event
    assert pub.calibration_id == calibration_id
    assert pub.revision_id == revision_id
    assert pub.outbound_permit_id == permit_id
    assert pub.signature_envelope_kind == envelope.kind
    assert pub.signing_version == signing_version
    assert pub.signature_bytes_hex == payload_bytes.hex()
    assert pub.signature_kid == signature_kid
    assert pub.receipt_id == receipt_id
    assert pub.published_at == now
    assert pub.occurred_at == now
    assert pub.published_by == actor_id
    assert pub.publication_status == "Live"

    rec = result.permit_event
    assert rec.permit_id == permit_id
    assert rec.content_hash == content_hash
    assert rec.home_stream_type == "Calibration"
    assert rec.home_stream_id == calibration_id
    assert rec.home_artifact_id == revision_id
    assert rec.receipt_id == receipt_id
    assert rec.recorded_at == now
    assert rec.occurred_at == now


@pytest.mark.unit
@given(
    calibration_id=st.uuids(),
    revision_id=st.uuids(),
    permit_id=st.uuids(),
    content_hash=_CONTENT_HASH,
    peer_facility_id=_PEER_FACILITY_ID,
    receipt_id=st.uuids(),
    payload_bytes=_PAYLOAD_BYTES,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decide_is_pure_same_inputs_yield_same_events(
    calibration_id: UUID,
    revision_id: UUID,
    permit_id: UUID,
    content_hash: str,
    peer_facility_id: str,
    receipt_id: UUID,
    payload_bytes: bytes,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Two calls with identical inputs produce equal event pairs.
    Detects clock leakage, hidden uuid4() calls, or non-determinism
    in the hex / hash transformations."""
    envelope = _envelope(payload_bytes, "cora/v1")
    permit = _permit(permit_id=permit_id, peer_facility_id=peer_facility_id, status="Active")
    state = _calibration(
        calibration_id=calibration_id,
        revisions=(
            _revision(
                revision_id=revision_id,
                content_hash=content_hash,
                established_at=now,
                established_by=ActorId(actor_id),
            ),
        ),
        actor_id=ActorId(actor_id),
        defined_at=now,
    )
    command = PublishCalibrationRevision(
        calibration_id=calibration_id,
        revision_id=revision_id,
        peer_facility_id=peer_facility_id,
    )
    first = decide(
        state,
        command,
        permit_result=permit,
        signature_envelope=envelope,
        signature_kid="kid",
        receipt_id=receipt_id,
        now=now,
        published_by=actor_id,
    )
    second = decide(
        state,
        command,
        permit_result=permit,
        signature_envelope=envelope,
        signature_kid="kid",
        receipt_id=receipt_id,
        now=now,
        published_by=actor_id,
    )
    assert first.calibration_event == second.calibration_event
    assert first.permit_event == second.permit_event
