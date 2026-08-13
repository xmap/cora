"""Domain events emitted by the Acquisition aggregate, plus the union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Single event ever emitted on an Acquisition stream:

  - `AcquisitionRecorded` (genesis-and-terminal): identity, the three
    cross-aggregate bindings, the dual-time pair, the settings /
    evidence carrier dicts, and the `recorded_by` attribution.

## Dual-time pattern on the payload

`occurred_at` is the CORA-side wall-clock when `record_acquisition`
ran (the in-memory state field is `recorded_at`, per the CORA
transversal-time convention). `captured_at` is a separate first-class
payload field carrying the instrument wall-clock. Both ship on the
payload; collapsing them would conflate two distinct evidentiary
tiers (PROV-O `generatedAtTime` vs `qualifiedGeneration`).

## Payload conventions

  - UUIDs serialize as strings; the optional `producing_run_id`
    serializes as null when None.
  - `settings` and `evidence` are JSON objects on disk (may be `{}`
    empty but never None). `evidence` is `AcquisitionEvidence`
    in-memory, not a bare dict: an evidence field left None is
    OMITTED from the object, never nulled, same as
    `ingest_scan.EVIDENCE_SCHEMA` before this VO replaced it.
  - Datetimes serialize via `.isoformat()`.
  - Status is NOT carried in the payload; the event type encodes it
    (AcquisitionRecorded -> RECORDED), same precedent as the rest of
    the codebase.

## Wire payload key ordering (pinned)

`acquisition_id`, `dataset_id`, `producing_asset_id`,
`producing_run_id`, `captured_at`, `settings`, `evidence`,
`occurred_at`, `recorded_by`.
"""

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.data.aggregates.acquisition.state import (
    AcquisitionEvidence,
    CapturedAtSource,
    validate_evidence,
)
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class AcquisitionRecorded:
    """A capture fact was recorded: a producing Asset captured bytes
    into a Dataset under an optional Run context.

    Status is implicit (`Recorded`); the evolver sets it. This is the
    only event the Acquisition aggregate ever emits.

    Per `docs/reference/modeling.md`'s event-VO carve-out: `evidence`
    is `AcquisitionEvidence`, not degraded to a bare `dict`, because
    the record exporter's generator recurses into a declared VO field
    by field but must drop an untyped `dict` opaque whole; see that VO
    for why it still recurses (not `ClosedValueObject`) rather than
    being kept whole. Every other field is a primitive (str, int, UUID,
    datetime) or `settings`, a JSON-object carrier dict with no known
    shape yet (see `Acquisition`'s "Settings and evidence" docstring).
    The dual-time pair carries `captured_at` (instrument wall-clock)
    alongside `occurred_at` (CORA-side wall-clock; the in-memory state
    field is `recorded_at`).

    Fold-symmetry attribution (every-fact-has-an-actor):
      - `recorded_by: ActorId`: the envelope `principal_id` of the
        record-slice caller. The PHYSICAL capturing entity is the
        `producing_asset_id` (a device); only the act of recording
        the fact needs an ActorId.
    """

    acquisition_id: UUID
    dataset_id: UUID
    producing_asset_id: UUID
    producing_run_id: UUID | None
    captured_at: datetime
    settings: dict[str, Any]
    evidence: AcquisitionEvidence
    occurred_at: datetime
    recorded_by: ActorId


# Discriminated union of every event the Acquisition aggregate emits.
# Single-arm today; widening only happens if a supersedence event ever
# fires (deliberately unfilled extension space).
AcquisitionEvent = AcquisitionRecorded


def event_type_name(event: AcquisitionEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: AcquisitionEvent) -> dict[str, Any]:
    """Serialize an Acquisition event to a JSON-friendly dict for jsonb."""
    match event:
        case AcquisitionRecorded(
            acquisition_id=acquisition_id,
            dataset_id=dataset_id,
            producing_asset_id=producing_asset_id,
            producing_run_id=producing_run_id,
            captured_at=captured_at,
            settings=settings,
            evidence=evidence,
            occurred_at=occurred_at,
            recorded_by=recorded_by,
        ):
            return {
                "acquisition_id": str(acquisition_id),
                "dataset_id": str(dataset_id),
                "producing_asset_id": str(producing_asset_id),
                "producing_run_id": (
                    str(producing_run_id) if producing_run_id is not None else None
                ),
                "captured_at": captured_at.isoformat(),
                "settings": settings,
                "evidence": _evidence_to_payload(evidence),
                "occurred_at": occurred_at.isoformat(),
                "recorded_by": str(recorded_by),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _evidence_to_payload(evidence: AcquisitionEvidence) -> dict[str, Any]:
    """Wire shape for `AcquisitionEvidence`: a JSON object with a key
    per non-None field, omitted (never nulled) when absent, matching
    the `ingest_scan.EVIDENCE_SCHEMA` convention this VO replaced.

    Iterates `dataclasses.fields` rather than a hand-maintained field
    list: a second, separately-maintained list here previously could
    silently drop a field from every published record if it fell out
    of sync with the dataclass (an addition to `AcquisitionEvidence`
    forgotten here), with no test able to catch it short of asserting
    every field by name.
    """
    payload: dict[str, Any] = {}
    for f in fields(evidence):
        raw = getattr(evidence, f.name)
        if raw is None:
            continue
        payload[f.name] = raw.value if isinstance(raw, CapturedAtSource) else raw
    return payload


def from_stored(stored: StoredEvent) -> AcquisitionEvent:
    """Rebuild an Acquisition event from a StoredEvent loaded from the store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than being silently dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "AcquisitionRecorded":

            def _build_recorded() -> AcquisitionRecorded:
                raw_producing_run_id = payload["producing_run_id"]
                return AcquisitionRecorded(
                    acquisition_id=UUID(payload["acquisition_id"]),
                    dataset_id=UUID(payload["dataset_id"]),
                    producing_asset_id=UUID(payload["producing_asset_id"]),
                    producing_run_id=(
                        UUID(raw_producing_run_id) if raw_producing_run_id is not None else None
                    ),
                    captured_at=datetime.fromisoformat(payload["captured_at"]),
                    settings=dict(payload["settings"]),
                    evidence=validate_evidence(payload["evidence"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    recorded_by=ActorId(UUID(payload["recorded_by"])),
                )

            return deserialize_or_raise("AcquisitionRecorded", _build_recorded, extra=(ValueError,))
        case _:
            msg = f"Unknown AcquisitionEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "AcquisitionEvent",
    "AcquisitionRecorded",
    "event_type_name",
    "from_stored",
    "to_payload",
]
