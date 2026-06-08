"""Domain events emitted by the Dataset aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.


  - `DatasetRegistered` (7a, genesis): identity, URI, checksum
    (algorithm + value), byte_size, encoding (media_type + sorted
    conforms_to list), producing_run_id, subject_id, derived_from
    (sorted UUID list), occurred_at.
  - `DatasetDiscarded` (7b, terminal): dataset_id, free-form
    `reason: str` (1-500 chars after trimming), occurred_at. Mirrors
    RunStopped / RunAborted / RunTruncated reason shape.

## Payload conventions

- UUIDs serialize as strings; UUID-set fields (`derived_from`)
  serialize as sorted string lists (matches the Policy precedent
  for set-semantic fields, so two registrations of the same logical
  Dataset produce byte-identical jsonb).
- `conforms_to` (in encoding) serializes as a sorted string list
  for the same reason.
- Optional refs (`producing_run_id`, `subject_id`) serialize as
  null when None.
- `encoding` serializes as a nested object: `{"media_type": str,
  "conforms_to": list[str]}`.
- `checksum` serializes as a nested object: `{"algorithm": str,
  "value": str}`.
- Status is NOT carried in the payload; the event type encodes it
  (DatasetRegistered → REGISTERED), same precedent as the rest of
  the codebase.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class DatasetRegistered:
    """A new Dataset was registered with the facility.

    Status is implicit (`Registered`); the evolver sets it. All
    cross-aggregate refs (`producing_run_id`, `subject_id`,
    `derived_from`) are eventual-consistency primitives.

    Per CONTRIBUTING.md "Primitives in event payloads": every field
    here is a primitive (str, int, UUID, datetime, frozenset of
    primitives). VOs (`DatasetChecksum`, `DatasetEncoding`) are
    reconstructed by the evolver on fold; the decider unwraps VOs
    before constructing the event.

    Trust-level additions (additive, forward-compat):
      - `producing_run_end_state: str | None`: Run's terminal status
        captured at registration when producing_run_id is set; None
        otherwise. Legacy events fold cleanly with this defaulting
        to None (payload.get).
      - `intent: str`: trust level (Intent.value); defaults to "Trial"
        on register. Legacy events fold cleanly with default "Trial".

    Calibration-citation addition (additive, forward-compat):
      - `used_calibration_ids: tuple[UUID, ...]`: revision-cited atomic
        IDs naming the CalibrationRevisions the reconstruction
        actually used (Calibration BC AsShot citation; symmetric to
        Run.pinned_calibration_ids). Tuple on the event payload for
        deterministic byte ordering on replay (the decider sorts
        before emit); the evolver reconstructs the frozenset.
        Pre-12c events fold cleanly with `payload.get(
        "used_calibration_ids", [])` returning an empty list.

    Fold-symmetry attribution (per [[project_fold_symmetry_design]]):
      - `registered_by: ActorId`: the envelope `principal_id` of the
        register-slice caller. Carried on the event payload so a future
        slice that opts into folding attribution onto Dataset state
        already has the data. Dataset stays fold-NEITHER on state per
        the Data BC entry in the fold-NEITHER allowlist (event payload
        carries the actor, aggregate state does not denorm).
    """

    dataset_id: UUID
    name: str
    uri: str
    checksum_algorithm: str
    checksum_value: str
    byte_size: int
    media_type: str
    conforms_to: frozenset[str]
    producing_run_id: UUID | None
    subject_id: UUID | None
    derived_from: frozenset[UUID]
    occurred_at: datetime
    registered_by: ActorId
    # additions:
    producing_run_end_state: str | None = None
    intent: str = "Trial"
    # Calibration BC AsShot citation; revision-cited
    # atomic-ID model per [[project_calibration_design]]. See state.py
    # for the full rationale. NO cross-BC existence check at the
    # decider (operator/agent supplies the citation set; symmetry
    # with Run.pinned_calibration_ids + the cross-BC eventual-
    # consistency stance). IMMUTABLE after register by aggregate-
    # level invariant (mirrors AsShot pattern). Forward-compat via
    # `payload.get("used_calibration_ids", [])` returning an empty
    # list for legacy streams lacking the field.
    used_calibration_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class DatasetPromoted:
    """A Dataset was promoted from Trial to Production intent.

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Mirrors DatasetDiscarded /
    RunStopped / RunAborted reason shape; same future-additive
    structured-taxonomy posture.

    Operationally this records "we're claiming this is publication-
    grade and here's why". The audit trail is immutable: the WHY
    survives forever even if the Dataset is later discarded.

    Fold-symmetry attribution (per [[project_fold_symmetry_design]]):
      - `promoted_by: ActorId`: the envelope `principal_id` of the
        promote-slice caller. Dataset stays fold-NEITHER on state.
    """

    dataset_id: UUID
    reason: str
    occurred_at: datetime
    promoted_by: ActorId


@dataclass(frozen=True)
class DatasetDiscarded:
    """A Dataset was discarded (Registered → Discarded terminal).

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Mirrors RunStopped /
    RunAborted / RunTruncated reason shape; same future-additive
    structured-taxonomy posture.

    GDPR-shaped: bytes at the URI are gone but this event keeps the
    metadata + reason for audit. The Discarded record itself does
    NOT capture the URI's deletion-time-state (operators may need
    to re-discover the original URI to re-run analysis chains); the
    URI lives on the prior DatasetRegistered event.

    Fold-symmetry attribution (per [[project_fold_symmetry_design]]):
      - `discarded_by: ActorId`: the envelope `principal_id` of the
        discard-slice caller. Dataset stays fold-NEITHER on state.
    """

    dataset_id: UUID
    reason: str
    occurred_at: datetime
    discarded_by: ActorId


@dataclass(frozen=True)
class DatasetDemoted:
    """A Dataset was demoted from Production to Retracted intent (post-Q4).

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Mirrors DatasetPromoted /
    DatasetDiscarded reason shape; same future-additive structured-
    taxonomy posture.

    Operationally this records "we're retracting this dataset's
    authoritative status because <X>". The audit trail is immutable:
    the WHY survives forever. First concrete instantiation of the
    Q4 compensation-primitive pattern (per [[project-dataset-demote-
    design]]; mirrors Crossref retraction model — additive notice,
    original DatasetPromoted preserved + marked).

    Audit linkage to the prior promote-driving Decision is OPTIONAL
    and lives on a paired Decision aggregate (operator authoring a
    Decision with `override_kind="invalidation"` + `parent_id` →
    prior promote-Decision). This event does NOT carry a Decision
    reference; the slice supports quick retraction during incident
    response without requiring a paired Decision first.

    Fold-symmetry attribution (per [[project_fold_symmetry_design]]):
      - `demoted_by: ActorId`: the envelope `principal_id` of the
        demote-slice caller. Dataset stays fold-NEITHER on state.
    """

    dataset_id: UUID
    reason: str
    occurred_at: datetime
    demoted_by: ActorId


# Discriminated union of every event the Dataset aggregate emits.
DatasetEvent = DatasetRegistered | DatasetDiscarded | DatasetPromoted | DatasetDemoted


def event_type_name(event: DatasetEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: DatasetEvent) -> dict[str, Any]:
    """Serialize a Dataset event to a JSON-friendly dict for jsonb storage.

    Set-semantic fields (`derived_from`, `encoding.conforms_to`)
    sort deterministically so two registrations of the same logical
    Dataset produce byte-identical jsonb.
    """
    match event:
        case DatasetRegistered(
            dataset_id=dataset_id,
            name=name,
            uri=uri,
            checksum_algorithm=checksum_algorithm,
            checksum_value=checksum_value,
            byte_size=byte_size,
            media_type=media_type,
            conforms_to=conforms_to,
            producing_run_id=producing_run_id,
            subject_id=subject_id,
            derived_from=derived_from,
            occurred_at=occurred_at,
            registered_by=registered_by,
            producing_run_end_state=producing_run_end_state,
            intent=intent,
            used_calibration_ids=used_calibration_ids,
        ):
            return {
                "dataset_id": str(dataset_id),
                "name": name,
                "uri": uri,
                "checksum": {
                    "algorithm": checksum_algorithm,
                    "value": checksum_value,
                },
                "byte_size": byte_size,
                "encoding": {
                    "media_type": media_type,
                    "conforms_to": sorted(conforms_to),
                },
                "producing_run_id": (
                    str(producing_run_id) if producing_run_id is not None else None
                ),
                "subject_id": str(subject_id) if subject_id is not None else None,
                "derived_from": sorted(str(d) for d in derived_from),
                "occurred_at": occurred_at.isoformat(),
                "registered_by": str(registered_by),
                # additions:
                "producing_run_end_state": producing_run_end_state,
                "intent": intent,
                # addition (sorted for deterministic jsonb bytes,
                # mirrors derived_from + Run.pinned_calibration_ids precedent).
                "used_calibration_ids": sorted(str(c) for c in used_calibration_ids),
            }
        case DatasetDiscarded(
            dataset_id=dataset_id,
            reason=reason,
            occurred_at=occurred_at,
            discarded_by=discarded_by,
        ):
            return {
                "dataset_id": str(dataset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
                "discarded_by": str(discarded_by),
            }
        case DatasetPromoted(
            dataset_id=dataset_id,
            reason=reason,
            occurred_at=occurred_at,
            promoted_by=promoted_by,
        ):
            return {
                "dataset_id": str(dataset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
                "promoted_by": str(promoted_by),
            }
        case DatasetDemoted(
            dataset_id=dataset_id,
            reason=reason,
            occurred_at=occurred_at,
            demoted_by=demoted_by,
        ):
            return {
                "dataset_id": str(dataset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
                "demoted_by": str(demoted_by),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> DatasetEvent:
    """Rebuild a Dataset event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "DatasetRegistered":

            def _build_registered() -> DatasetRegistered:
                raw_producing_run_id = payload["producing_run_id"]
                raw_subject_id = payload["subject_id"]
                raw_checksum = payload["checksum"]
                raw_encoding = payload["encoding"]
                return DatasetRegistered(
                    dataset_id=UUID(payload["dataset_id"]),
                    name=payload["name"],
                    uri=payload["uri"],
                    checksum_algorithm=raw_checksum["algorithm"],
                    checksum_value=raw_checksum["value"],
                    byte_size=int(payload["byte_size"]),
                    media_type=raw_encoding["media_type"],
                    conforms_to=frozenset(raw_encoding["conforms_to"]),
                    producing_run_id=(
                        UUID(raw_producing_run_id) if raw_producing_run_id is not None else None
                    ),
                    subject_id=UUID(raw_subject_id) if raw_subject_id is not None else None,
                    derived_from=frozenset(UUID(d) for d in payload["derived_from"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    registered_by=ActorId(UUID(payload["registered_by"])),
                    producing_run_end_state=payload.get("producing_run_end_state"),
                    intent=payload.get("intent", "Trial"),
                    used_calibration_ids=tuple(
                        UUID(c) for c in payload.get("used_calibration_ids", [])
                    ),
                )

            return deserialize_or_raise("DatasetRegistered", _build_registered)
        case "DatasetDiscarded":
            return deserialize_or_raise(
                "DatasetDiscarded",
                lambda: DatasetDiscarded(
                    dataset_id=UUID(payload["dataset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    discarded_by=ActorId(UUID(payload["discarded_by"])),
                ),
            )
        case "DatasetPromoted":
            return deserialize_or_raise(
                "DatasetPromoted",
                lambda: DatasetPromoted(
                    dataset_id=UUID(payload["dataset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    promoted_by=ActorId(UUID(payload["promoted_by"])),
                ),
            )
        case "DatasetDemoted":
            return deserialize_or_raise(
                "DatasetDemoted",
                lambda: DatasetDemoted(
                    dataset_id=UUID(payload["dataset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    demoted_by=ActorId(UUID(payload["demoted_by"])),
                ),
            )
        case _:
            msg = f"Unknown DatasetEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "DatasetDemoted",
    "DatasetDiscarded",
    "DatasetEvent",
    "DatasetPromoted",
    "DatasetRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
