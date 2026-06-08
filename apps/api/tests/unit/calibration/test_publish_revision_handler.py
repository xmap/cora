"""Unit tests for the publish_revision handler (Stage 3d3 canary).

Exercise the handler end-to-end against in-memory publish + signature
+ permit-lookup adapters. Asserts the cross-BC append_streams contract:
exactly one Calibration event + one Permit event landed in a single
transaction (single position-window in the InMemory event store).
"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.calibration.aggregates.calibration import (
    CalibrationStatus,
    event_type_name,
    to_payload,
)
from cora.calibration.aggregates.calibration.events import (
    CalibrationDefined,
    CalibrationRevisionAppended,
)
from cora.calibration.errors import PublishPortNotWiredError, UnauthorizedError
from cora.calibration.features.publish_revision import (
    PublishCalibrationRevision,
    bind,
)
from cora.federation.adapters.in_memory_permit_lookup import InMemoryPermitLookup
from cora.federation.adapters.in_memory_publish_port import InMemoryPublishPort
from cora.federation.adapters.in_memory_signature_port import InMemorySignaturePort
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import StreamAppend
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_PEER = "aps-2bm"
_CALIBRATION_ID = UUID("33333333-3333-3333-3333-333333333333")
_REVISION_ID = UUID("44444444-4444-4444-4444-444444444444")
_PRINCIPAL_ID = ActorId(UUID("55555555-5555-5555-5555-555555555555"))
_TARGET_ID = UUID("88888888-8888-8888-8888-888888888888")
_CORRELATION_ID = UUID("99999999-9999-9999-9999-999999999999")
_PERMIT_ID = UUID("11111111-1111-1111-1111-111111111111")
_PERMIT_VERSION = 0  # empty stream in unit tests; PG production lookup mirrors real version


async def _seed_calibration(
    deps: Kernel,
    *,
    revision_content_hash: str | None = "a" * 64,
) -> None:
    defined = CalibrationDefined(
        calibration_id=_CALIBRATION_ID,
        target_id=_TARGET_ID,
        quantity="rotation_center_pixels",
        operating_point={},
        description=None,
        defined_by=_PRINCIPAL_ID,
        occurred_at=_NOW,
    )
    appended = CalibrationRevisionAppended(
        revision_id=_REVISION_ID,
        calibration_id=_CALIBRATION_ID,
        value={"value": 1.0},
        status=CalibrationStatus.VERIFIED,
        source_procedure_id=None,
        source_dataset_id=None,
        asserted_by=ActorId(uuid4()),
        established_at=_NOW,
        established_by=_PRINCIPAL_ID,
        decided_by_decision_id=None,
        supersedes_revision_id=None,
        occurred_at=_NOW,
        content_hash=revision_content_hash,
    )
    new_events = [
        to_new_event(
            event_type=event_type_name(event),
            payload=to_payload(event),
            occurred_at=event.occurred_at,
            event_id=uuid4(),
            command_name="seed",
            correlation_id=_CORRELATION_ID,
            causation_id=None,
            principal_id=_PRINCIPAL_ID,
        )
        for event in (defined, appended)
    ]
    await deps.event_store.append_streams(
        [
            StreamAppend(
                stream_type="Calibration",
                stream_id=_CALIBRATION_ID,
                expected_version=0,
                events=new_events,
            ),
        ]
    )


def _build_publish_deps(
    *,
    permit_lookup: InMemoryPermitLookup | None = None,
    publish_port: InMemoryPublishPort | None = None,
    signature_port: InMemorySignaturePort | None = None,
    deny: bool = False,
    ids: list[UUID] | None = None,
) -> tuple[Kernel, InMemoryPermitLookup, InMemoryPublishPort, InMemorySignaturePort]:
    pl = permit_lookup or InMemoryPermitLookup()
    pp = publish_port or InMemoryPublishPort()
    sp = signature_port or InMemorySignaturePort()
    deps = build_deps(ids=ids, deny=deny, now=_NOW)
    deps = replace(deps, permit_lookup=pl, publish_port=pp, signature_port=sp)
    return deps, pl, pp, sp


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


def test_bind_raises_when_all_publish_deps_explicitly_unset_on_kernel() -> None:
    deps = build_deps()
    deps = replace(deps, publish_port=None, signature_port=None, permit_lookup=None)
    with pytest.raises(PublishPortNotWiredError) as exc_info:
        bind(deps)
    assert set(exc_info.value.missing) == {
        "publish_port",
        "signature_port",
        "permit_lookup",
    }


def test_bind_with_only_some_deps_unset_lists_only_the_missing_ones() -> None:
    deps = build_deps()
    deps = replace(deps, signature_port=None, permit_lookup=None)
    with pytest.raises(PublishPortNotWiredError) as exc_info:
        bind(deps)
    assert "publish_port" not in exc_info.value.missing
    assert "signature_port" in exc_info.value.missing
    assert "permit_lookup" in exc_info.value.missing


@pytest.mark.asyncio
async def test_handler_happy_path_returns_receipt_id_and_writes_both_streams() -> None:
    deps, pl, _pp, _sp = _build_publish_deps(ids=[uuid4() for _ in range(8)])
    pl.register_outbound(
        peer_facility_id=_PEER,
        artifact_kind="CalibrationRevision",
        permit_id=_PERMIT_ID,
        current_version=_PERMIT_VERSION,
    )
    await _seed_calibration(deps)
    handler = bind(deps)

    receipt_id = await handler(
        _command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID
    )

    assert isinstance(receipt_id, UUID)
    cal_events, _ = await deps.event_store.load("Calibration", _CALIBRATION_ID)
    publication_events = [e for e in cal_events if e.event_type == "CalibrationRevisionPublished"]
    assert len(publication_events) == 1
    assert publication_events[0].payload["calibration_id"] == str(_CALIBRATION_ID)
    assert publication_events[0].payload["revision_id"] == str(_REVISION_ID)
    assert publication_events[0].payload["outbound_permit_id"] == str(_PERMIT_ID)
    assert publication_events[0].payload["publication_status"] == "Live"
    assert publication_events[0].payload["receipt_id"] == str(receipt_id)
    assert publication_events[0].payload["published_by"] == str(_PRINCIPAL_ID)

    permit_events, _ = await deps.event_store.load("Permit", _PERMIT_ID)
    recorded = [e for e in permit_events if e.event_type == "PublicationReceiptRecorded"]
    assert len(recorded) == 1
    assert recorded[0].payload["receipt_id"] == str(receipt_id)
    assert recorded[0].payload["home_stream_id"] == str(_CALIBRATION_ID)
    assert recorded[0].payload["home_artifact_id"] == str(_REVISION_ID)
    assert recorded[0].payload["content_hash"] == "a" * 64


@pytest.mark.asyncio
async def test_handler_writes_both_events_in_a_single_transaction() -> None:
    deps, pl, _, _ = _build_publish_deps(ids=[uuid4() for _ in range(8)])
    pl.register_outbound(
        peer_facility_id=_PEER,
        artifact_kind="CalibrationRevision",
        permit_id=_PERMIT_ID,
        current_version=_PERMIT_VERSION,
    )
    await _seed_calibration(deps)
    handler = bind(deps)
    await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    cal_events, _ = await deps.event_store.load("Calibration", _CALIBRATION_ID)
    permit_events, _ = await deps.event_store.load("Permit", _PERMIT_ID)
    publication_event = next(
        e for e in cal_events if e.event_type == "CalibrationRevisionPublished"
    )
    receipt_event = next(e for e in permit_events if e.event_type == "PublicationReceiptRecorded")
    assert publication_event.transaction_id == receipt_event.transaction_id


@pytest.mark.asyncio
async def test_handler_records_one_published_artifact_on_publish_port_per_call() -> None:
    deps, pl, pp, _ = _build_publish_deps(ids=[uuid4() for _ in range(8)])
    pl.register_outbound(
        peer_facility_id=_PEER,
        artifact_kind="CalibrationRevision",
        permit_id=_PERMIT_ID,
        current_version=_PERMIT_VERSION,
    )
    await _seed_calibration(deps)
    handler = bind(deps)
    await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    published = pp.published_artifacts()
    assert len(published) == 1
    artifact = published[0]
    assert artifact.payload_type == "application/vnd.cora.calibration-revision-published+json"
    assert artifact.canonicalization_version == "cora/v1"
    assert artifact.signature_envelope.kind == "dsse_static_jwks"
    assert artifact.canonical_bytes.startswith(b"DSSEv1 ")


@pytest.mark.asyncio
async def test_handler_raises_unauthorized_when_authz_denies() -> None:
    deps, pl, _, _ = _build_publish_deps(deny=True, ids=[uuid4() for _ in range(8)])
    pl.register_outbound(
        peer_facility_id=_PEER,
        artifact_kind="CalibrationRevision",
        permit_id=_PERMIT_ID,
        current_version=_PERMIT_VERSION,
    )
    await _seed_calibration(deps)
    handler = bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)


@pytest.mark.asyncio
async def test_handler_short_circuits_when_calibration_missing() -> None:
    deps, pl, _, _ = _build_publish_deps(ids=[uuid4() for _ in range(8)])
    pl.register_outbound(
        peer_facility_id=_PEER,
        artifact_kind="CalibrationRevision",
        permit_id=_PERMIT_ID,
        current_version=_PERMIT_VERSION,
    )
    handler = bind(deps)
    from cora.calibration.aggregates.calibration import CalibrationNotFoundError

    with pytest.raises(CalibrationNotFoundError):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)


@pytest.mark.asyncio
async def test_handler_short_circuits_when_outbound_permit_inactive() -> None:
    deps, pl, _, _ = _build_publish_deps(ids=[uuid4() for _ in range(8)])
    pl.register_outbound(
        peer_facility_id=_PEER,
        artifact_kind="CalibrationRevision",
        permit_id=_PERMIT_ID,
        status="Suspended",
        current_version=_PERMIT_VERSION,
    )
    await _seed_calibration(deps)
    handler = bind(deps)
    from cora.calibration.aggregates.calibration import OutboundPermitNotActiveError

    with pytest.raises(OutboundPermitNotActiveError) as exc_info:
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)
    assert exc_info.value.status == "Suspended"


@pytest.mark.asyncio
async def test_handler_short_circuits_when_revision_missing_content_hash() -> None:
    deps, pl, _, _ = _build_publish_deps(ids=[uuid4() for _ in range(8)])
    pl.register_outbound(
        peer_facility_id=_PEER,
        artifact_kind="CalibrationRevision",
        permit_id=_PERMIT_ID,
        current_version=_PERMIT_VERSION,
    )
    await _seed_calibration(deps, revision_content_hash=None)
    handler = bind(deps)
    from cora.calibration.aggregates.calibration import (
        CalibrationCannotPublishRevisionError,
    )

    with pytest.raises(CalibrationCannotPublishRevisionError):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)


@pytest.mark.asyncio
async def test_handler_signature_envelope_persisted_round_trips_signing_version_via_hex() -> None:
    deps, pl, _, _ = _build_publish_deps(ids=[uuid4() for _ in range(8)])
    pl.register_outbound(
        peer_facility_id=_PEER,
        artifact_kind="CalibrationRevision",
        permit_id=_PERMIT_ID,
        current_version=_PERMIT_VERSION,
    )
    await _seed_calibration(deps)
    handler = bind(deps)
    await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    cal_events, _ = await deps.event_store.load("Calibration", _CALIBRATION_ID)
    publication = next(e for e in cal_events if e.event_type == "CalibrationRevisionPublished")
    assert publication.payload["signing_version"] == "cora/v1"
    assert publication.payload["signature_envelope_kind"] == "dsse_static_jwks"
    bytes.fromhex(publication.payload["signature_bytes_hex"])  # round-trips
