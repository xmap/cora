"""Pure decider for the `PublishCalibrationRevision` command.

Cross-BC federation decider. Validates the loaded Calibration
aggregate + the looked-up outbound Permit, then emits two events to
be persisted atomically by the handler via `EventStore.append_streams`:

  - `CalibrationRevisionPublished` onto the Calibration stream
  - `PublicationReceiptRecorded` onto the matching outbound Permit stream

The decider stays pure: handler-injected parameters carry the
SignatureEnvelope (from SignaturePort.sign), the receipt_id (from
PublishPort.publish), the wall-clock `now`, and the
published_by_actor_id (from the request envelope's principal_id).
The decider's job is to validate the publication is authorized +
deterministic, then transform the inputs into the locked event
shapes.

Invariants:
  - Calibration state must not be None -> `CalibrationNotFoundError`
  - Named revision must exist on aggregate.revisions ->
    `CalibrationRevisionNotFoundError`
  - Revision must carry a non-null content_hash ->
    `CalibrationCannotPublishRevisionError`
  - PermitLookup must return an Active outbound Permit ->
    `OutboundPermitNotActiveError` (covers miss + non-Active status)

## What the decider does NOT validate

  - DCO chain shape: enforced at the verify-then-apply orchestrator
    when the artifact is re-verified on the consumer side, plus the
    architecture-fitness test that walks publish_* handlers asserting
    `published_by_actor_id` resolves to a human Actor. The handler
    composes the chain from the envelope principal at publish time;
    the decider trusts that handler.
  - Permit's terms allowing this artifact kind: the handler-tier
    PermitLookup resolves outbound permits keyed on (peer_facility_id,
    artifact_kind), so the lookup hitting at all is the kind-match
    evidence. A future iteration may move this check earlier when
    the lookup widens to return the matched terms.
  - Signature shape: the SignaturePort.sign call already enforces
    the envelope-vs-canonicalization-version invariant; the decider
    trusts the envelope it receives.
  - Idempotency of repeated publish: a follow-up iteration adds a
    state-folded `is_published` check; today the decider always emits
    new events on every call (handler is expected to wrap with
    Idempotency-Key per the AppendRevision precedent).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from cora.calibration.aggregates.calibration import (
    Calibration,
    CalibrationCannotPublishRevisionError,
    CalibrationNotFoundError,
    CalibrationRevision,
    CalibrationRevisionNotFoundError,
    CalibrationRevisionPublished,
    OutboundPermitNotActiveError,
)
from cora.calibration.features.publish_revision.command import (
    PublishCalibrationRevision,
)
from cora.federation.aggregates.permit.events import PublicationReceiptRecorded
from cora.infrastructure.ports.federation import (
    PermitLookupResult,
    SignatureEnvelope,
)

_HOME_STREAM_TYPE = "Calibration"
_PUBLICATION_STATUS_LIVE = "Live"


@dataclass(frozen=True)
class PublishRevisionEvents:
    """Cross-BC event pair the handler appends atomically.

    `calibration_event` lands on the Calibration stream;
    `permit_event` lands on the outbound Permit stream. Both share
    the same `receipt_id` for cross-stream audit joins.
    """

    calibration_event: CalibrationRevisionPublished
    permit_event: PublicationReceiptRecorded


def decide(
    state: Calibration | None,
    command: PublishCalibrationRevision,
    *,
    permit_result: PermitLookupResult | None,
    signature_envelope: SignatureEnvelope,
    signature_kid: str,
    receipt_id: UUID,
    now: datetime,
    published_by_actor_id: UUID,
) -> PublishRevisionEvents:
    """Validate the publish + emit the cross-BC event pair.

    Invariants:
      - Calibration state must not be None -> CalibrationNotFoundError
      - Named revision must exist on aggregate.revisions ->
        CalibrationRevisionNotFoundError
      - Revision must carry a non-null content_hash ->
        CalibrationCannotPublishRevisionError
      - PermitLookup must return an Active outbound Permit ->
        OutboundPermitNotActiveError (covers miss + non-Active status)
    """
    if state is None:
        raise CalibrationNotFoundError(command.calibration_id)

    revision = _find_revision(state, command.revision_id)
    if revision is None:
        raise CalibrationRevisionNotFoundError(
            calibration_id=command.calibration_id,
            revision_id=command.revision_id,
        )
    if revision.content_hash is None:
        raise CalibrationCannotPublishRevisionError(
            calibration_id=command.calibration_id,
            revision_id=command.revision_id,
        )

    if permit_result is None:
        raise OutboundPermitNotActiveError(
            peer_facility_id=command.peer_facility_id,
            artifact_kind="CalibrationRevision",
            status="<unresolved>",
        )
    if permit_result.status != "Active":
        raise OutboundPermitNotActiveError(
            peer_facility_id=command.peer_facility_id,
            artifact_kind="CalibrationRevision",
            status=permit_result.status,
        )

    calibration_event = CalibrationRevisionPublished(
        calibration_id=command.calibration_id,
        revision_id=command.revision_id,
        outbound_permit_id=permit_result.permit_id,
        signature_envelope_kind=signature_envelope.kind,
        signing_version=signature_envelope.signing_version,
        signature_bytes_hex=signature_envelope.payload_bytes.hex(),
        signature_kid=signature_kid,
        receipt_id=receipt_id,
        published_at=now,
        published_by_actor_id=published_by_actor_id,
        publication_status=_PUBLICATION_STATUS_LIVE,
        occurred_at=now,
    )
    permit_event = PublicationReceiptRecorded(
        permit_id=permit_result.permit_id,
        content_hash=revision.content_hash,
        home_stream_type=_HOME_STREAM_TYPE,
        home_stream_id=command.calibration_id,
        home_artifact_id=command.revision_id,
        receipt_id=receipt_id,
        recorded_at=now,
        occurred_at=now,
    )
    return PublishRevisionEvents(
        calibration_event=calibration_event,
        permit_event=permit_event,
    )


def _find_revision(state: Calibration, revision_id: UUID) -> CalibrationRevision | None:
    for revision in state.revisions:
        if revision.revision_id == revision_id:
            return revision
    return None


__all__ = ["PublishRevisionEvents", "decide"]
