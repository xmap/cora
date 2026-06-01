"""Domain events emitted by the Calibration aggregate, plus the discriminated union.

Two events shipped at BC genesis:

  - `CalibrationDefined`           -- genesis (no revisions yet)
  - `CalibrationRevisionAppended`  -- append-only revision growth

`operating_point` and `value` travel as JSON-friendly dicts (jsonb on
disk). Postgres jsonb canonicalises key order + dedups duplicate keys
+ compares numbers by value (Q6 lock). The serialise / deserialise
helpers bridge typed VOs <-> wire only for the polymorphic source.

## Polymorphic source (Q5 lock): exclusive-arc serialization

`CalibrationSource` is a 3-arm tagged union (MeasuredSource /
ComputedSource / AssertedSource) on the aggregate. On the event
payload it serialises as three nullable id fields with exactly one
non-null (Postgres exclusive-arc consensus + Christensen/Hashrocket
recommendation). The serialize / deserialize helpers below are
PUBLIC cross-slice helpers (no leading underscore): the
`append_calibration_revision` decider uses `serialize_source` to build the event
payload; the evolver uses `deserialize_source` to reconstruct the
typed union from the payload.

### Wire-shape divergence from Caution / Safety (deliberate)

Caution's `serialize_target` and Safety's `serialize_binding` emit a
nested `{"kind": "<ArmName>", "id": "<uuid>"}` object inside the event
payload. Calibration deliberately inlines exclusive-arc fields
(`source_procedure_id` / `source_dataset_id` / `source_actor_id`)
directly into the event payload instead. Reason: the same
exclusive-arc shape lands in the projection's
`proj_calibration_revisions` table per Q5 lock, so keeping wire and
projection-column shapes symmetric simplifies the projection-write
code path (one structural transform instead of two). The
aggregate's typed `CalibrationSource` union is the in-memory
representation; both wire layers below it (event payload + projection
columns) use exclusive-arc. The convergence point with Caution /
Safety is the typed in-aggregate VO, NOT the wire serialization.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.calibration.aggregates.calibration.state import (
    AssertedSource,
    CalibrationSource,
    CalibrationStatus,
    ComputedSource,
    InvalidCalibrationSourceError,
    MeasuredSource,
)
from cora.infrastructure.event_payload import deserialize_or_raise, deserialize_vo_or_raise
from cora.infrastructure.ports.event_store import StoredEvent

# ---------------------------------------------------------------------------
# CalibrationSource serialize / deserialize (public cross-slice helpers)
# ---------------------------------------------------------------------------


def serialize_source(source: CalibrationSource) -> dict[str, Any]:
    """Encode a typed CalibrationSource into exclusive-arc payload fields.

    Returns a dict with three keys, exactly one non-null:

      MeasuredSource(procedure_id=X)  -> {procedure_id: str(X), dataset_id: None, actor_id: None}
      ComputedSource(dataset_id=Y)    -> {procedure_id: None, dataset_id: str(Y), actor_id: None}
      AssertedSource(actor_id=Z)      -> {procedure_id: None, dataset_id: None, actor_id: str(Z)}
    """
    match source:
        case MeasuredSource(procedure_id=procedure_id):
            return {
                "source_procedure_id": str(procedure_id),
                "source_dataset_id": None,
                "source_actor_id": None,
            }
        case ComputedSource(dataset_id=dataset_id):
            return {
                "source_procedure_id": None,
                "source_dataset_id": str(dataset_id),
                "source_actor_id": None,
            }
        case AssertedSource(actor_id=actor_id):
            return {
                "source_procedure_id": None,
                "source_dataset_id": None,
                "source_actor_id": str(actor_id),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(source)


def deserialize_source(payload: dict[str, Any]) -> CalibrationSource:
    """Decode exclusive-arc payload fields into a typed CalibrationSource.

    Validates that exactly one of `source_procedure_id` /
    `source_dataset_id` / `source_actor_id` is non-null. Raises
    `InvalidCalibrationSourceError` on violation (zero set, more than
    one set, or all three missing keys) so a contaminated payload fails
    loud rather than silently degrading to the first non-null match.
    """

    def _build() -> CalibrationSource:
        procedure_id_raw = payload.get("source_procedure_id")
        dataset_id_raw = payload.get("source_dataset_id")
        actor_id_raw = payload.get("source_actor_id")
        present = [
            ("source_procedure_id", procedure_id_raw),
            ("source_dataset_id", dataset_id_raw),
            ("source_actor_id", actor_id_raw),
        ]
        non_null = [(k, v) for k, v in present if v is not None]
        if len(non_null) != 1:
            msg = (
                f"CalibrationSource payload must have exactly one non-null "
                f"source_*_id field; got {len(non_null)} non-null: "
                f"{[k for k, _ in non_null]!r}"
            )
            raise InvalidCalibrationSourceError(msg)
        key, value = non_null[0]
        match key:
            case "source_procedure_id":
                return MeasuredSource(procedure_id=UUID(value))
            case "source_dataset_id":
                return ComputedSource(dataset_id=UUID(value))
            case "source_actor_id":
                return AssertedSource(actor_id=UUID(value))
            case _:  # pragma: no cover  # exhaustiveness guard via len-check above
                msg = f"Unknown source_*_id key {key!r}"
                raise InvalidCalibrationSourceError(msg)

    return deserialize_vo_or_raise(
        "CalibrationSource",
        _build,
        raise_as=InvalidCalibrationSourceError,
    )


# ---------------------------------------------------------------------------
# Event classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationDefined:
    """A new Calibration was defined (genesis; no revisions yet).

    `operating_point` is the JSON-shaped dict identifying this
    calibration's regime; validated against the quantity's
    operating_point_schema at the decider.

    `description` is optional operator-prose; `None` when absent
    (matches Method/Plan/Family precedent).

    `defined_by_actor_id` denorm of the envelope `principal_id` for
    projection convenience; consumers querying "calibrations I
    defined" don't need to join the envelope table.
    """

    calibration_id: UUID
    target_id: UUID
    quantity: str  # CalibrationQuantity value-string
    operating_point: dict[str, Any]
    description: str | None
    defined_by_actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class CalibrationRevisionAppended:
    """A new revision was appended to an existing Calibration.

    `value` is the JSON-shaped dict for the revision; validated against
    the quantity's value_schema at the decider.

    `status` is the per-revision CalibrationStatus enum
    (`Provisional` | `Verified`); `.value` is the wire-payload string.

    The three `source_*_id` fields are the exclusive-arc serialization
    of the typed CalibrationSource union: exactly one non-null at
    decoder time. See `serialize_source` / `deserialize_source`.

    `decided_by_decision_id` mirrors the AdjustRun / StartRun /
    AbortRun cross-BC eventual-consistency pattern: OPTIONAL; NOT
    validated against the Decision BC at write time.

    `supersedes_revision_id` is OPTIONAL; when set, must reference a
    revision already on this aggregate (cross-aggregate supersession
    is forbidden).

    `established_by_actor_id` denorm of envelope `principal_id`.
    """

    revision_id: UUID
    calibration_id: UUID
    value: dict[str, Any]
    status: CalibrationStatus
    source_procedure_id: UUID | None
    source_dataset_id: UUID | None
    source_actor_id: UUID | None
    established_at: datetime
    established_by_actor_id: UUID
    decided_by_decision_id: UUID | None
    supersedes_revision_id: UUID | None
    occurred_at: datetime
    # SHA-256 of the canonical body bytes for the revision's content
    # subset; computed at the decider per [[project_content_addressed_identity_design]].
    # None for pre-rollout legacy events (additive-event pattern; same
    # posture as PlanVersioned.content_hash). Projected onto
    # proj_calibration_summary.latest_revision_content_hash for
    # equivalence lookups; folded onto CalibrationRevision.content_hash.
    content_hash: str | None = None


@dataclass(frozen=True)
class CalibrationRevisionPublished:
    """A revision was published to the federation surface under an outbound permit.

    Cross-BC iter-b federation event. Records the publication action
    on the Calibration stream; the matching `PublicationReceiptRecorded`
    on the Permit stream (Federation BC) lands atomically via the
    handler's `EventStore.append_streams` call per cross-BC append-
    streams discipline.

    Per [[project_federation_port_design]]:
      - `signature_envelope_kind` is the SignatureEnvelope union
        discriminator at port-tier; one of "dsse_static_jwks",
        "dsse_sigstore_keyless", "cose_sign1_scitt" today.
      - `signing_version` is the signing-recipe identifier per
        [[project_canonicalization_port_design]] (the v1 default
        is "cora/v1"); the verifier dispatches to the matching
        SigningPort adapter via the SigningRegistry.
      - `signature_bytes_hex` is the raw signature bytes encoded as
        hex string for jsonb storage; the verifier decodes with
        `bytes.fromhex(...)`.
      - `signature_kid` is the adapter-specific key identifier.
      - `receipt_id` is the UUID minted by the PublishPort adapter
        (the cross-BC `PublicationReceiptRecorded` on the Permit
        stream carries the same receipt_id for join purposes).
      - `published_by_actor_id` is the envelope `principal_id` of
        the publish-slice caller (for human-initiated publish);
        AI agent publication goes through `promote_*_publication`
        per the propose-then-promote pattern, and the handler
        resolves the human promoter's actor_id.
      - `publication_status` is the FSM position at publish time;
        "Live" today. Yanked / Withdrawn transitions land in a
        follow-up iteration.

    State-folding posture (Stage 3d2 canary): the evolver records
    this event as a no-op fold on Calibration state today; the
    publication block on `CalibrationRevision` is deferred to
    Stage 3d3 alongside the projection write-path. The event is
    the source of truth; aggregate read-back of publication
    metadata lands when the projection materializes.
    """

    calibration_id: UUID
    revision_id: UUID
    outbound_permit_id: UUID
    signature_envelope_kind: str
    signing_version: str
    signature_bytes_hex: str
    signature_kid: str
    receipt_id: UUID
    published_at: datetime
    published_by_actor_id: UUID
    publication_status: str
    occurred_at: datetime


# Discriminated union of every event the Calibration aggregate emits.
CalibrationEvent = CalibrationDefined | CalibrationRevisionAppended | CalibrationRevisionPublished


def event_type_name(event: CalibrationEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: CalibrationEvent) -> dict[str, Any]:
    """Serialise a Calibration event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings. The `operating_point` and `value` dicts are written
    verbatim (Postgres jsonb canonicalises on insert per Q6 lock).
    """
    match event:
        case CalibrationDefined(
            calibration_id=calibration_id,
            target_id=target_id,
            quantity=quantity,
            operating_point=operating_point,
            description=description,
            defined_by_actor_id=defined_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "calibration_id": str(calibration_id),
                "target_id": str(target_id),
                "quantity": quantity,
                "operating_point": operating_point,
                "description": description,
                "defined_by_actor_id": str(defined_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case CalibrationRevisionAppended(
            revision_id=revision_id,
            calibration_id=calibration_id,
            value=value,
            status=status,
            source_procedure_id=source_procedure_id,
            source_dataset_id=source_dataset_id,
            source_actor_id=source_actor_id,
            established_at=established_at,
            established_by_actor_id=established_by_actor_id,
            decided_by_decision_id=decided_by_decision_id,
            supersedes_revision_id=supersedes_revision_id,
            occurred_at=occurred_at,
            content_hash=content_hash,
        ):
            payload: dict[str, Any] = {
                "revision_id": str(revision_id),
                "calibration_id": str(calibration_id),
                "value": value,
                "status": status.value,
                "source_procedure_id": (
                    str(source_procedure_id) if source_procedure_id is not None else None
                ),
                "source_dataset_id": (
                    str(source_dataset_id) if source_dataset_id is not None else None
                ),
                "source_actor_id": (str(source_actor_id) if source_actor_id is not None else None),
                "established_at": established_at.isoformat(),
                "established_by_actor_id": str(established_by_actor_id),
                "decided_by_decision_id": (
                    str(decided_by_decision_id) if decided_by_decision_id is not None else None
                ),
                "supersedes_revision_id": (
                    str(supersedes_revision_id) if supersedes_revision_id is not None else None
                ),
                "occurred_at": occurred_at.isoformat(),
            }
            if content_hash is not None:
                payload["content_hash"] = content_hash
            return payload
        case CalibrationRevisionPublished(
            calibration_id=calibration_id,
            revision_id=revision_id,
            outbound_permit_id=outbound_permit_id,
            signature_envelope_kind=signature_envelope_kind,
            signing_version=signing_version,
            signature_bytes_hex=signature_bytes_hex,
            signature_kid=signature_kid,
            receipt_id=receipt_id,
            published_at=published_at,
            published_by_actor_id=published_by_actor_id,
            publication_status=publication_status,
            occurred_at=occurred_at,
        ):
            return {
                "calibration_id": str(calibration_id),
                "revision_id": str(revision_id),
                "outbound_permit_id": str(outbound_permit_id),
                "signature_envelope_kind": signature_envelope_kind,
                "signing_version": signing_version,
                "signature_bytes_hex": signature_bytes_hex,
                "signature_kid": signature_kid,
                "receipt_id": str(receipt_id),
                "published_at": published_at.isoformat(),
                "published_by_actor_id": str(published_by_actor_id),
                "publication_status": publication_status,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> CalibrationEvent:
    """Rebuild a Calibration event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "CalibrationDefined":
            return deserialize_or_raise(
                "CalibrationDefined",
                lambda: CalibrationDefined(
                    calibration_id=UUID(payload["calibration_id"]),
                    target_id=UUID(payload["target_id"]),
                    quantity=payload["quantity"],
                    operating_point=payload["operating_point"],
                    description=payload.get("description"),
                    defined_by_actor_id=UUID(payload["defined_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "CalibrationRevisionAppended":

            def _build_revision_appended() -> CalibrationRevisionAppended:
                raw_proc = payload.get("source_procedure_id")
                raw_dataset = payload.get("source_dataset_id")
                raw_actor = payload.get("source_actor_id")
                raw_decided = payload.get("decided_by_decision_id")
                raw_supersedes = payload.get("supersedes_revision_id")
                return CalibrationRevisionAppended(
                    revision_id=UUID(payload["revision_id"]),
                    calibration_id=UUID(payload["calibration_id"]),
                    value=payload["value"],
                    status=CalibrationStatus(payload["status"]),
                    source_procedure_id=UUID(raw_proc) if raw_proc is not None else None,
                    source_dataset_id=UUID(raw_dataset) if raw_dataset is not None else None,
                    source_actor_id=UUID(raw_actor) if raw_actor is not None else None,
                    established_at=datetime.fromisoformat(payload["established_at"]),
                    established_by_actor_id=UUID(payload["established_by_actor_id"]),
                    decided_by_decision_id=UUID(raw_decided) if raw_decided is not None else None,
                    supersedes_revision_id=(
                        UUID(raw_supersedes) if raw_supersedes is not None else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    content_hash=payload.get("content_hash"),
                )

            return deserialize_or_raise(
                "CalibrationRevisionAppended",
                _build_revision_appended,
                extra=(ValueError,),
            )
        case "CalibrationRevisionPublished":

            def _build_revision_published() -> CalibrationRevisionPublished:
                return CalibrationRevisionPublished(
                    calibration_id=UUID(payload["calibration_id"]),
                    revision_id=UUID(payload["revision_id"]),
                    outbound_permit_id=UUID(payload["outbound_permit_id"]),
                    signature_envelope_kind=payload["signature_envelope_kind"],
                    signing_version=payload["signing_version"],
                    signature_bytes_hex=payload["signature_bytes_hex"],
                    signature_kid=payload["signature_kid"],
                    receipt_id=UUID(payload["receipt_id"]),
                    published_at=datetime.fromisoformat(payload["published_at"]),
                    published_by_actor_id=UUID(payload["published_by_actor_id"]),
                    publication_status=payload["publication_status"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise(
                "CalibrationRevisionPublished",
                _build_revision_published,
                extra=(ValueError,),
            )
        case unknown:
            msg = f"Unknown Calibration event type: {unknown!r}"
            raise ValueError(msg)


__all__ = [
    "CalibrationDefined",
    "CalibrationEvent",
    "CalibrationRevisionAppended",
    "CalibrationRevisionPublished",
    "deserialize_source",
    "event_type_name",
    "from_stored",
    "serialize_source",
    "to_payload",
]
