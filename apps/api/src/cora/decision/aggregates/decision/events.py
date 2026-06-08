"""Domain events emitted by the Decision aggregate.


Three events:

  - `DecisionRegistered` (8a, genesis): the Decision itself.
  - `DecisionLogbookOpened` (8c-a): declares an attached
    observation logbook (kind + schema). Mirrors the Conduit
    BC's logbook-open event. At-most-one-open-per-
    kind enforced by the evolver.
  - `DecisionLogbookClosed` (8c-a): terminates a logbook.
    Strict-not-idempotent: re-closing raises.

Corrections, exceptions, appeals, and supersessions land as NEW
Decisions with `parent_id` pointing at the original and
`override_kind` explaining the transition. There is no
DecisionUpdated / DecisionRevoked / DecisionCorrected event.

## Payload conventions

  - UUIDs serialize as strings.
  - Optional fields serialize as null when None.
  - `alternatives` serializes as a list[str] preserving caller
    order (AI deciders need top-k ordering; Cedar / OPA both
    preserve it).
  - `inputs` serializes as a JSON object; callers are
    responsible for ensuring values round-trip through json.dumps
    (the BC enforces shape, not value primitiveness).
  - Status is implicit (a Decision is final once registered);
    chain semantics are projection concerns, not event-payload
    concerns.

## PROV-AGENT field-name alignment (gate-review L13)

  - `decided_by` ↔ `prov:wasAssociatedWith.agent`
  - `parent_id` ↔ `prov:wasInformedBy`
  - `occurred_at` ↔ `prov:atTime`

PROV-O export at the API boundary lands when first consumer asks
(deferred-with-trigger); the in-domain payload stays on these
primitives. The PROV-O alias mapping
(`decided_by -> prov:wasAssociatedWith.agent`) is performed in the
edge serializer when that adapter ships, not on the in-domain payload.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.decision.aggregates.decision.state import (
    DecisionConfidenceSource,
    DecisionOverrideKind,
    DecisionRating,
)
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId
from cora.shared.logbook import LogbookSchema


@dataclass(frozen=True)
class DecisionRegistered:
    """A new Decision was registered.

    All fields except `id`, `decided_by`, `context`, `choice`, and
    `occurred_at` are optional. `override_kind` requires `parent_id`
    (enforced at the decider).
    """

    decision_id: UUID
    decided_by: ActorId
    context: str
    choice: str
    parent_id: UUID | None
    override_kind: DecisionOverrideKind | None
    rule: str | None
    reasoning: str | None
    confidence: float | None
    confidence_source: DecisionConfidenceSource | None
    alternatives: tuple[str, ...]
    inputs: dict[str, Any] | None
    reasoning_signature: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class DecisionLogbookOpened:
    """An observation logbook was attached to a Decision.

    `kind` discriminates the logbook category (today only
    `LOGBOOK_KIND_REASONING` from state.py); `schema` declares the
    entry-row shape per Bluesky's EventDescriptor pattern. The
    schema lives on the event so projections can read entry shape
    uniformly without per-BC adapters.

    At-most-one-open-per-kind enforced by the evolver: opening a
    second logbook of an existing kind raises
    `DecisionLogbookAlreadyOpenError`.
    """

    decision_id: UUID
    logbook_id: UUID
    kind: str
    schema: LogbookSchema
    occurred_at: datetime


@dataclass(frozen=True)
class DecisionLogbookClosed:
    """An observation logbook was closed (no further entries).

    Strict-not-idempotent: re-closing raises
    `DecisionLogbookNotOpenError`. Closing an unknown logbook id
    raises the same error.
    """

    decision_id: UUID
    logbook_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class DecisionRated:
    """An operator rated a Decision (acceptance-signal capture).

    Multiple `DecisionRated` events per (decision, actor) pair are
    allowed; the evolver folds latest-per-actor wins into
    `Decision.ratings: dict[UUID, DecisionRatingRecord]`. The audit
    trail (every rating ever submitted) lives in the event log;
    the aggregate / projection carry the latest snapshot.

    `comment` is optional. Empty / whitespace-only comments are
    rejected at the validator (callers pass None to omit).

    `rated_at` is the DOMAIN timestamp (when the operator submitted
    the rating per their wall-clock); `occurred_at` is the
    ENVELOPE timestamp (the same value at write time, kept distinct
    per the cross-BC envelope-field convention; see
    [[project-naming-conventions]] and the
    `ClearanceReviewStepAppended` `decided_at` + `occurred_at`
    precedent). At write time the two values are equal by
    construction; downstream consumers prefer `rated_at` for
    domain-aware queries and `occurred_at` for envelope-bound
    audit / ordering.

    `confidence_at_rating` captures the rated Decision's
    `confidence` value at the instant the rating was recorded
    (gate-review cross-BC P2-4: payload-borne avoids the cross-
    projection read race that the original projection-side denorm
    would suffer under rebuild). Null when the rated Decision has
    no confidence value. The handler captures this from
    `Decision.state.confidence` at write time (`capture, don't
    recompute` principle from
    [[project-non-determinism-principle]]).

    The rating actor's identity lives on the payload as
    `rated_by` for denorm convenience; the
    `StoredEvent.principal_id` envelope carries the same value at
    write time (every rating is self-recorded; no spoof path).
    """

    decision_id: UUID
    rating: DecisionRating
    comment: str | None
    rated_by: ActorId
    rated_at: datetime
    occurred_at: datetime
    confidence_at_rating: float | None


# 8c-a expands the union with the two logbook lifecycle events.
# 8f-b adds DecisionRated for operator acceptance-signal capture.
DecisionEvent = DecisionRegistered | DecisionLogbookOpened | DecisionLogbookClosed | DecisionRated


def event_type_name(event: DecisionEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: DecisionEvent) -> dict[str, Any]:
    """Serialize a Decision event to a JSON-friendly dict for jsonb.

    In-domain payload uses CORA primitives (`decided_by`, `parent_id`,
    `occurred_at`). The PROV-O alias mapping
    (`decided_by -> prov:wasAssociatedWith.agent`,
    `parent_id -> prov:wasInformedBy`, `occurred_at -> prov:atTime`)
    lives at the RDF serializer edge (PROV-O export adapter), not here;
    this keeps the BC boundary stable when PROV consumers land.
    """
    match event:
        case DecisionRegistered(
            decision_id=decision_id,
            decided_by=decided_by,
            context=context,
            choice=choice,
            parent_id=parent_id,
            override_kind=override_kind,
            rule=rule,
            reasoning=reasoning,
            confidence=confidence,
            confidence_source=confidence_source,
            alternatives=alternatives,
            inputs=inputs,
            reasoning_signature=reasoning_signature,
            occurred_at=occurred_at,
        ):
            return {
                "decision_id": str(decision_id),
                "decided_by": str(decided_by),
                "context": context,
                "choice": choice,
                "parent_id": str(parent_id) if parent_id is not None else None,
                "override_kind": override_kind,
                "rule": rule,
                "reasoning": reasoning,
                "confidence": confidence,
                "confidence_source": (
                    confidence_source.value if confidence_source is not None else None
                ),
                # Caller-supplied order preserved (top-k ordering matters).
                "alternatives": list(alternatives),
                "inputs": inputs,
                "reasoning_signature": reasoning_signature,
                "occurred_at": occurred_at.isoformat(),
            }
        case DecisionLogbookOpened(
            decision_id=decision_id,
            logbook_id=logbook_id,
            kind=kind,
            schema=schema,
            occurred_at=occurred_at,
        ):
            return {
                "decision_id": str(decision_id),
                "logbook_id": str(logbook_id),
                "kind": kind,
                "schema": schema.to_dict(),
                "occurred_at": occurred_at.isoformat(),
            }
        case DecisionLogbookClosed(
            decision_id=decision_id,
            logbook_id=logbook_id,
            occurred_at=occurred_at,
        ):
            return {
                "decision_id": str(decision_id),
                "logbook_id": str(logbook_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case DecisionRated(
            decision_id=decision_id,
            rating=rating,
            comment=comment,
            rated_by=rated_by,
            rated_at=rated_at,
            occurred_at=occurred_at,
            confidence_at_rating=confidence_at_rating,
        ):
            return {
                "decision_id": str(decision_id),
                "rating": rating.value,
                "comment": comment,
                "rated_by": str(rated_by),
                "rated_at": rated_at.isoformat(),
                "occurred_at": occurred_at.isoformat(),
                "confidence_at_rating": confidence_at_rating,
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> DecisionEvent:
    """Rebuild a Decision event from a StoredEvent."""
    payload = stored.payload
    match stored.event_type:
        case "DecisionRegistered":

            def _build_registered() -> DecisionRegistered:
                raw_parent = payload["parent_id"]
                raw_override = payload["override_kind"]
                raw_conf_source = payload["confidence_source"]
                return DecisionRegistered(
                    decision_id=UUID(payload["decision_id"]),
                    decided_by=ActorId(UUID(payload["decided_by"])),
                    context=payload["context"],
                    choice=payload["choice"],
                    parent_id=UUID(raw_parent) if raw_parent is not None else None,
                    override_kind=raw_override,
                    rule=payload["rule"],
                    reasoning=payload["reasoning"],
                    confidence=payload["confidence"],
                    confidence_source=(
                        DecisionConfidenceSource(raw_conf_source)
                        if raw_conf_source is not None
                        else None
                    ),
                    alternatives=tuple(payload["alternatives"]),
                    inputs=payload["inputs"],
                    reasoning_signature=payload["reasoning_signature"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("DecisionRegistered", _build_registered)
        case "DecisionLogbookOpened":
            return deserialize_or_raise(
                "DecisionLogbookOpened",
                lambda: DecisionLogbookOpened(
                    decision_id=UUID(payload["decision_id"]),
                    logbook_id=UUID(payload["logbook_id"]),
                    kind=payload["kind"],
                    schema=LogbookSchema.from_dict(payload["schema"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "DecisionLogbookClosed":
            return deserialize_or_raise(
                "DecisionLogbookClosed",
                lambda: DecisionLogbookClosed(
                    decision_id=UUID(payload["decision_id"]),
                    logbook_id=UUID(payload["logbook_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "DecisionRated":

            def _build_rated() -> DecisionRated:
                rated_at = datetime.fromisoformat(payload["rated_at"])
                occurred_at_raw = payload.get("occurred_at")
                return DecisionRated(
                    decision_id=UUID(payload["decision_id"]),
                    rating=DecisionRating(payload["rating"]),
                    comment=payload.get("comment"),
                    rated_by=ActorId(UUID(payload["rated_by"])),
                    rated_at=rated_at,
                    occurred_at=(
                        datetime.fromisoformat(occurred_at_raw)
                        if occurred_at_raw is not None
                        else rated_at
                    ),
                    confidence_at_rating=payload.get("confidence_at_rating"),
                )

            return deserialize_or_raise("DecisionRated", _build_rated)
        case _:
            msg = f"Unknown DecisionEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "DecisionEvent",
    "DecisionLogbookClosed",
    "DecisionLogbookOpened",
    "DecisionRated",
    "DecisionRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
