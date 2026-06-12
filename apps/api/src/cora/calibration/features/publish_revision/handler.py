"""Application handler for the `publish_revision` slice.

Cross-BC iter-b federation handler. Loads the Calibration aggregate
+ the matching outbound Permit via PermitLookup, canonicalizes the
artifact via the deployment-default Canonicalizer, signs via
SignaturePort, publishes via PublishPort, and atomically appends the
event pair onto both streams via `EventStore.append_streams`.

Per project_federation_port_design.md Section 'Cross-BC atomic writes':
two streams, one transaction. The handler short-circuits on any
decider domain error before any port IO; the SignaturePort.sign and
PublishPort.publish calls happen ONLY after the pre-flight pure
decider has validated the publish is authorized + deterministic.

Per AH#17 + arch-2: SignaturePort.sign delegates to ByteSigner for
raw crypto; the handler does not invoke a crypto library directly.
The artifact's `content_hash` is reused verbatim from the revision
state per the content-addressed-identity rollout (no port-side
canonicalization re-recompute).

Kernel deps consumed:
  - authz: authorize the publish command before any IO
  - event_store: load both aggregates + append_streams the pair
  - permit_lookup: resolve the outbound Permit by (peer, artifact_kind)
  - canonicalization_registry: resolve the default adapter for sign
  - signature_port: sign canonicalized bytes under trust context
  - publish_port: publish the artifact and receive the receipt
  - clock + id_generator: server-side wall-clock + receipt_id

Production wiring (Kernel construction site, follow-up commit):
PermitLookup -> PostgresPermitLookup (reads
proj_federation_permit_summary); SignaturePort + PublishPort wire
to InMemory adapters today (test substitute until the rule-of-two
trigger fires per [[project_federation_port_design]]).
"""

from typing import Protocol
from uuid import UUID

from cora.calibration.aggregates.calibration import (
    CalibrationNotFoundError,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.calibration.aggregates.calibration.evolver import fold
from cora.calibration.errors import PublishPortNotWiredError, UnauthorizedError
from cora.calibration.features.publish_revision.command import (
    PublishCalibrationRevision,
)
from cora.calibration.features.publish_revision.decider import (
    PublishRevisionEvents,
    decide,
)
from cora.federation.aggregates.permit import event_type_name as permit_event_type_name
from cora.federation.aggregates.permit import to_payload as permit_to_payload
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.ports.federation import (
    CredentialRef,
    FederationTrustContext,
    PublishedArtifact,
    SignatureEnvelope,
    SignedOffBy,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.facility_code import FacilityCode

_STREAM_TYPE_CALIBRATION = "Calibration"
_STREAM_TYPE_PERMIT = "Permit"
_COMMAND_NAME = "PublishCalibrationRevision"
_ARTIFACT_KIND = "CalibrationRevision"
_PAYLOAD_TYPE = "application/vnd.cora.calibration-revision-published+json"
_SCHEMA_VERSION = 1

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare publish_revision handler returned by `bind()`."""

    async def __call__(
        self,
        command: PublishCalibrationRevision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """publish_revision handler with Idempotency-Key support.

    `with_idempotency` at wire.py wraps the bare Handler; retries
    with the same key + body return the cached receipt_id instead
    of double-publishing.
    """

    async def __call__(
        self,
        command: PublishCalibrationRevision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a publish_revision handler closed over the shared deps.

    Raises `PublishPortNotWiredError` when any of the publish-side
    deps are absent so misconfiguration surfaces at startup time.
    """
    missing = tuple(
        name
        for name, value in (
            ("publish_port", deps.publish_port),
            ("signature_port", deps.signature_port),
            ("permit_lookup", deps.permit_lookup),
        )
        if value is None
    )
    if missing:
        raise PublishPortNotWiredError(missing=missing)
    publish_port = deps.publish_port
    signature_port = deps.signature_port
    permit_lookup = deps.permit_lookup
    assert publish_port is not None
    assert signature_port is not None
    assert permit_lookup is not None

    async def handler(
        command: PublishCalibrationRevision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "publish_revision.start",
            command_name=_COMMAND_NAME,
            calibration_id=str(command.calibration_id),
            revision_id=str(command.revision_id),
            peer_facility_id=command.peer_facility_id,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "publish_revision.denied",
                command_name=_COMMAND_NAME,
                calibration_id=str(command.calibration_id),
                revision_id=str(command.revision_id),
                principal_id=str(principal_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored_cal, cal_version = await deps.event_store.load(
            _STREAM_TYPE_CALIBRATION, command.calibration_id
        )
        state = fold([from_stored(s) for s in stored_cal])
        if state is None:
            raise CalibrationNotFoundError(command.calibration_id)

        # Construct FacilityCode VO at the port edge per Slice 3 of
        # project_structural_scope_design. The command DTO carries the
        # peer_facility_id as a bare string (wire-payload-immutability
        # constraint); the port surface consumes the typed VO.
        peer_facility_code = FacilityCode(command.peer_facility_id)
        permit_result = await permit_lookup.lookup_outbound(
            peer_facility_id=peer_facility_code, artifact_kind=_ARTIFACT_KIND
        )

        revision = next((r for r in state.revisions if r.revision_id == command.revision_id), None)
        content_hash_hex = (
            revision.content_hash if revision is not None and revision.content_hash else ""
        )
        canonicalization_adapter = deps.canonicalization_registry.resolve(
            deps.canonicalization_registry.default_version()
        )
        canonicalized = canonicalization_adapter.canonicalize(
            _PAYLOAD_TYPE,
            {
                "calibration_id": str(command.calibration_id),
                "revision_id": str(command.revision_id),
                "content_hash": content_hash_hex,
            },
        )

        trust_context = _build_trust_context(permit_result, command.peer_facility_id)
        signature_envelope: SignatureEnvelope = await signature_port.sign(
            canonicalized, trust_context
        )

        receipt_id = deps.id_generator.new_id()
        now = deps.clock.now()

        artifact = _build_published_artifact(
            command=command,
            revision_content_hash=content_hash_hex,
            canonical_bytes=canonicalized.bytes_,
            envelope=signature_envelope,
            published_at=now,
            published_by=principal_id,
            permit_abi_tier_floor=(
                permit_result.abi_tier_floor if permit_result is not None else "Stable"
            ),
            canonicalization_version=canonicalized.adapter_version,
        )
        await publish_port.publish(artifact)

        events: PublishRevisionEvents = decide(
            state,
            command,
            permit_result=permit_result,
            signature_envelope=signature_envelope,
            signature_kid=_extract_kid(signature_envelope),
            receipt_id=receipt_id,
            now=now,
            published_by=principal_id,
        )

        assert permit_result is not None  # decide raises before this line if None
        calibration_new_event = to_new_event(
            event_type=event_type_name(events.calibration_event),
            payload=to_payload(events.calibration_event),
            occurred_at=events.calibration_event.occurred_at,
            event_id=deps.id_generator.new_id(),
            command_name=_COMMAND_NAME,
            correlation_id=correlation_id,
            causation_id=causation_id,
            principal_id=principal_id,
        )
        permit_new_event = to_new_event(
            event_type=permit_event_type_name(events.permit_event),
            payload=permit_to_payload(events.permit_event),
            occurred_at=events.permit_event.occurred_at,
            event_id=deps.id_generator.new_id(),
            command_name=_COMMAND_NAME,
            correlation_id=correlation_id,
            causation_id=causation_id,
            principal_id=principal_id,
        )

        await deps.event_store.append_streams(
            [
                StreamAppend(
                    stream_type=_STREAM_TYPE_CALIBRATION,
                    stream_id=command.calibration_id,
                    expected_version=cal_version,
                    events=[calibration_new_event],
                ),
                StreamAppend(
                    stream_type=_STREAM_TYPE_PERMIT,
                    stream_id=permit_result.permit_id,
                    expected_version=permit_result.current_version,
                    events=[permit_new_event],
                ),
            ]
        )

        _log.info(
            "publish_revision.success",
            command_name=_COMMAND_NAME,
            calibration_id=str(command.calibration_id),
            revision_id=str(command.revision_id),
            receipt_id=str(receipt_id),
            outbound_permit_id=str(permit_result.permit_id),
        )
        return receipt_id

    return handler


def _build_trust_context(
    permit_result: object | None, peer_facility_id: str
) -> FederationTrustContext:
    abi_tier_floor = getattr(permit_result, "abi_tier_floor", "Stable")
    return FederationTrustContext(
        permit_id=getattr(permit_result, "permit_id", NIL_SENTINEL_ID),
        allowed_credentials=frozenset[CredentialRef](),
        allowed_payload_types=frozenset({_PAYLOAD_TYPE}),
        abi_tier_floor=abi_tier_floor,
    )


def _build_published_artifact(
    *,
    command: PublishCalibrationRevision,
    revision_content_hash: str,
    canonical_bytes: bytes,
    envelope: SignatureEnvelope,
    published_at: object,
    published_by: UUID,
    permit_abi_tier_floor: str,
    canonicalization_version: str,
) -> PublishedArtifact:
    from datetime import datetime

    assert isinstance(published_at, datetime)
    return PublishedArtifact(
        content_hash=(bytes.fromhex(revision_content_hash) if revision_content_hash else b""),
        canonical_bytes=canonical_bytes,
        payload_type=_PAYLOAD_TYPE,
        signature_envelope=envelope,
        source_facility_id=command.calibration_id,
        published_at=published_at,
        expires_at=None,
        abi_tier=permit_abi_tier_floor,
        dco_chain=(SignedOffBy(actor_id=published_by, signed_at=published_at),),
        schema_version=_SCHEMA_VERSION,
        canonicalization_version=canonicalization_version,
    )


def _extract_kid(envelope: SignatureEnvelope) -> str:
    return getattr(envelope, "kid", "in-memory-kid")


__all__ = [
    "Handler",
    "IdempotentHandler",
    "bind",
]
