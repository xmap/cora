"""Domain events emitted by the Shortfall aggregate, plus the union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Single event ever emitted on a Shortfall stream:

  - `ShortfallRecorded` (genesis-and-terminal): identity, the two
    cross-aggregate bindings, the frame accounting, the closed reason,
    the finality pair and the `recorded_by` attribution.

## Payload conventions

  - UUIDs serialize as strings; the two optional counts serialize as
    null when None.
  - `reason` serializes as its `StrEnum` value, a closed vocabulary
    that can never embed a path (see `ShortfallReason`).
  - Datetimes serialize via `.isoformat()`.
  - Status is NOT carried in the payload; the event type encodes it
    (ShortfallRecorded -> RECORDED), same precedent as the rest of the
    codebase.

## Wire payload key ordering (pinned)

`shortfall_id`, `producing_run_id`, `capture_path_id`, `host`, `root`,
`projection_count`, `commanded_projection_count`, `dropped_frame_count`,
`reason`, `file_modified_at`, `run_ended_at`, `occurred_at`,
`recorded_by`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.data.aggregates.shortfall.state import ShortfallReason
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class ShortfallRecorded:
    """A capture was found to have produced something that can never
    become a Dataset.

    Status is implicit (`Recorded`); the evolver sets it. This is the
    only event the Shortfall aggregate ever emits.

    Every field is a primitive (str, int, UUID, datetime) or the closed
    `ShortfallReason` enum. There is no carrier dict and no
    free-text field anywhere on this payload, deliberately: the refusal
    messages this fact replaces embed the opened path verbatim, and the
    row cannot be erased, so the payload is kept to shapes that cannot
    carry one.

    `producing_run_id` is NOT optional, unlike `AcquisitionRecorded`'s.
    The finality judgement is defined against the Run's terminal, so a
    Shortfall without a Run has no evidence that the file is done
    changing and must not be recorded at all.

    Fold-symmetry attribution (every-fact-has-an-actor):
      - `recorded_by: ActorId`: the envelope `principal_id` of the
        caller whose ingest attempt surfaced this. In practice the
        `CaptureScanIngestor` agent, but a human hitting the same
        refusal through the ordinary route records it identically.
    """

    shortfall_id: UUID
    producing_run_id: UUID
    capture_path_id: UUID
    host: str
    root: str
    projection_count: int
    commanded_projection_count: int | None
    dropped_frame_count: int | None
    reason: ShortfallReason
    file_modified_at: datetime
    run_ended_at: datetime
    occurred_at: datetime
    recorded_by: ActorId


# Discriminated union of every event the Shortfall aggregate emits.
# Single-arm today; widening only happens if a retraction event ever
# fires (deliberately unfilled extension space, same posture as
# `AcquisitionEvent`).
ShortfallEvent = ShortfallRecorded


def event_type_name(event: ShortfallEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: ShortfallEvent) -> dict[str, Any]:
    """Serialize a Shortfall event to a JSON-friendly dict for jsonb."""
    match event:
        case ShortfallRecorded(
            shortfall_id=shortfall_id,
            producing_run_id=producing_run_id,
            capture_path_id=capture_path_id,
            host=host,
            root=root,
            projection_count=projection_count,
            commanded_projection_count=commanded_projection_count,
            dropped_frame_count=dropped_frame_count,
            reason=reason,
            file_modified_at=file_modified_at,
            run_ended_at=run_ended_at,
            occurred_at=occurred_at,
            recorded_by=recorded_by,
        ):
            return {
                "shortfall_id": str(shortfall_id),
                "producing_run_id": str(producing_run_id),
                "capture_path_id": str(capture_path_id),
                "host": host,
                "root": root,
                "projection_count": projection_count,
                "commanded_projection_count": commanded_projection_count,
                "dropped_frame_count": dropped_frame_count,
                "reason": reason.value,
                "file_modified_at": file_modified_at.isoformat(),
                "run_ended_at": run_ended_at.isoformat(),
                "occurred_at": occurred_at.isoformat(),
                "recorded_by": str(recorded_by),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ShortfallEvent:
    """Rebuild a Shortfall event from a StoredEvent loaded from the store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than being silently dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "ShortfallRecorded":

            def _build_recorded() -> ShortfallRecorded:
                raw_commanded = payload["commanded_projection_count"]
                raw_dropped = payload["dropped_frame_count"]
                return ShortfallRecorded(
                    shortfall_id=UUID(payload["shortfall_id"]),
                    producing_run_id=UUID(payload["producing_run_id"]),
                    capture_path_id=UUID(payload["capture_path_id"]),
                    host=payload["host"],
                    root=payload["root"],
                    projection_count=int(payload["projection_count"]),
                    commanded_projection_count=(
                        int(raw_commanded) if raw_commanded is not None else None
                    ),
                    dropped_frame_count=(int(raw_dropped) if raw_dropped is not None else None),
                    reason=ShortfallReason(payload["reason"]),
                    file_modified_at=datetime.fromisoformat(payload["file_modified_at"]),
                    run_ended_at=datetime.fromisoformat(payload["run_ended_at"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    recorded_by=ActorId(UUID(payload["recorded_by"])),
                )

            return deserialize_or_raise("ShortfallRecorded", _build_recorded, extra=(ValueError,))
        case _:
            msg = f"Unknown ShortfallEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ShortfallEvent",
    "ShortfallRecorded",
    "event_type_name",
    "from_stored",
    "to_payload",
]
