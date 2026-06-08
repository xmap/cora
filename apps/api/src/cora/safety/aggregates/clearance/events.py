"""Domain events emitted by the Clearance aggregate, plus the discriminated union.

Event catalog: `ClearanceRegistered` (genesis -> Defined); the 6
FSM-closure events (Submitted / ReviewStarted / ReviewStepAppended /
Approved / Rejected / Activated); the 3 terminal/amendment events
(Expired / AmendmentInitiated / Superseded). Same
event-introduction-per-cohort precedent as Supply and Operation.

Status is NOT carried in `ClearanceRegistered`'s payload -- the event
type IS the state-change indicator (matches `FamilyDefined ->
DEFINED`, `SubjectMounted -> MOUNTED`, `SupplyRegistered -> UNKNOWN`).

`bindings`, `declarations`, `risk_band` travel in the genesis payload
as primitive-encoded structures (see `serialize_bindings` and
`serialize_declarations` for the JSON shape). The evolver reconstructs
typed VOs.

`kind` and `risk_band` travel as primitive strings (StrEnum values);
the evolver reconstructs via `ClearanceKind(payload["kind"])` and
`RiskBand(payload["risk_band"]) if payload.get("risk_band") else None`.

The 4 typed ClearanceBinding arms (Subject / Asset / Run / Procedure)
encode as `{"kind": "Subject", "id": "<uuid>"}` etc.; ExternalRefBinding
encodes as `{"kind": "External", "scheme": "...", "value": "..."}` (the
discriminator value `"External"` stays per [[project_identifier_vo_design]];
only the inner payload key renamed `id -> value` to match the shared
Identifier VO wire shape). The evolver dispatches on the `"kind"`
discriminator. Same shape pattern as ClearanceBinding's typed-arm-vs-
ExternalRefBinding split is preserved on the wire.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise, deserialize_vo_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.safety.aggregates.clearance.hazard_classification import (
    GHSPictogram,
    HazardClassification,
    NFPA704Rating,
    RiskBand,
    SchemeCode,
)
from cora.safety.aggregates.clearance.state import (
    AssetBinding,
    ClearanceBinding,
    ExternalRefBinding,
    HazardDeclaration,
    ProcedureBinding,
    RunBinding,
    SubjectBinding,
)
from cora.shared.identifier import Identifier
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class ClearanceRegistered:
    """A new safety-form clearance was registered.

    Status is implicit (`Defined`) -- the evolver sets it. Per the
    cross-aggregate genesis-event convention, the event type IS the
    state-change indicator.

    Carries the full Clearance shape at registration time:
    `kind / title / bindings / declarations / risk_band /
    external_id? / valid_from? / valid_until? / parent_id?`.

    `parent_id` is non-None only for Clearances registered via the
    `amend_clearance` slice. For `register_clearance`, parent_id is
    always None.
    """

    clearance_id: UUID
    kind: str
    facility_asset_id: UUID
    title: str
    bindings: tuple[dict[str, Any], ...]
    declarations: tuple[dict[str, Any], ...]
    risk_band: str | None
    external_id: str | None
    valid_from: datetime | None
    valid_until: datetime | None
    parent_id: UUID | None
    occurred_at: datetime


@dataclass(frozen=True)
class ClearanceSubmitted:
    """The clearance was submitted for review (`Defined -> Submitted`)."""

    clearance_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ClearanceReviewStarted:
    """The first reviewer picked up the clearance (`Submitted -> UnderReview`).

    `first_reviewer_role` is the facility-vocabulary label for the first
    step in the review chain (for example, `BeamlineScientist`, `LocalContact`).
    Captured for audit clarity; subsequent steps land via
    `ClearanceReviewStepAppended`.
    """

    clearance_id: UUID
    first_reviewer_role: str
    occurred_at: datetime


@dataclass(frozen=True)
class ClearanceReviewStepAppended:
    """One reviewer step appended to the chain (no status change).

    Status stays `UnderReview` until terminal step decides Approved or
    Rejected via the dedicated `approve_clearance` / `reject_clearance`
    slices. The review_steps tuple grows by one ReviewStep per event.
    """

    clearance_id: UUID
    step_index: int
    role: str
    decided_by: ActorId
    decision: str
    decided_at: datetime
    notes: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class ClearanceApproved:
    """All required reviewers approved (`UnderReview -> Approved`).

    Optional `valid_from` / `valid_until` overrides defaults set at
    register time; carried in payload for audit clarity.

    Approving actor's identity lives on the envelope (`StoredEvent.
    principal_id`), not the payload, per cross-BC `RunAborted` /
    `ProcedureAborted` precedent. The projection reads the envelope
    at apply time to populate `last_reviewed_by`.
    """

    clearance_id: UUID
    valid_from: datetime | None
    valid_until: datetime | None
    occurred_at: datetime


@dataclass(frozen=True)
class ClearanceRejected:
    """The clearance was rejected during review (`UnderReview -> Rejected`).

    `reason` is operator-supplied free-form prose, 1-500 chars after trim
    (mirrors RunAbortReason / SupplyReason / etc. precedent).

    Rejecting actor's identity lives on the envelope (`StoredEvent.
    principal_id`), not the payload.
    """

    clearance_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class ClearanceActivated:
    """The clearance became effective (`Approved -> Active`).

    Separate event from Approved to model APS ESAF "approved but not yet
    effective" + DESY DOOR "approved but awaiting beamtime start". The
    transition is the operator's gesture asserting the clearance is
    in-force; gating logic checks `status == Active`.
    """

    clearance_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ClearanceExpired:
    """The clearance's validity ended (`Active -> Expired`).

    Operator-action only today; auto-expiry on `valid_until` is
    deferred per watch #7 in [[project_safety_clearance_design]].

    `reason` is operator-supplied free-form prose, 1-500 chars after
    trim (mirrors RunAbortReason / ClearanceRejected precedent).
    Expiring actor lives on `StoredEvent.principal_id` envelope.
    """

    clearance_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class ClearanceSuperseded:
    """The clearance was replaced by an amended child (`Active -> Superseded`).

    Written to the PARENT clearance's stream alongside the child's
    `ClearanceRegistered` via `EventStore.append_streams` (atomic
    two-stream commit). The `by_clearance_id` field carries the new
    child clearance's id so the parent->child link is queryable
    without crossing streams.

    Per modern event-sourcing convention (single event per transition
    with causation metadata; see Dudycz, Khononov 2025): no separate
    `AmendmentInitiated` intent event. Causation_id on the envelope
    links the two events back to the originating `amend_clearance`
    command. The superseding actor lives on `StoredEvent.principal_id`.
    """

    clearance_id: UUID
    by_clearance_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Clearance aggregate emits.
# ClearanceRegistered (genesis).
# 6 FSM-closure events (Submit/StartReview/AppendReviewStep/Approve/Reject/Activate).
# 2 terminal events (Expired/Superseded). The amend slice
# atomically writes parent's Superseded + child's Registered via
# EventStore.append_streams; the originally-planned AmendmentInitiated
# event was dropped as redundant (Superseded.by_clearance_id carries
# the same link).
ClearanceEvent = (
    ClearanceRegistered
    | ClearanceSubmitted
    | ClearanceReviewStarted
    | ClearanceReviewStepAppended
    | ClearanceApproved
    | ClearanceRejected
    | ClearanceActivated
    | ClearanceExpired
    | ClearanceSuperseded
)


def event_type_name(event: ClearanceEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


# ---------------------------------------------------------------------------
# Serialization helpers (binding / classification primitives <-> typed VOs)
#
# Public (no leading underscore) because the route layer + decider also use
# these to bridge wire shape <-> typed VOs. Dropping the underscore signals
# that they are the sanctioned cross-slice helpers, not aggregate-private.
# ---------------------------------------------------------------------------


def serialize_binding(binding: ClearanceBinding) -> dict[str, Any]:
    """Encode a typed ClearanceBinding to a JSON-friendly dict.

    The dict carries a `"kind"` discriminator plus the binding-specific
    fields (id for typed-arm refs; scheme + value for ExternalRefBinding,
    flattening the wrapped `Identifier`).
    """
    match binding:
        case SubjectBinding(subject_id=subject_id):
            return {"kind": "Subject", "id": str(subject_id)}
        case AssetBinding(asset_id=asset_id):
            return {"kind": "Asset", "id": str(asset_id)}
        case RunBinding(run_id=run_id):
            return {"kind": "Run", "id": str(run_id)}
        case ProcedureBinding(procedure_id=procedure_id):
            return {"kind": "Procedure", "id": str(procedure_id)}
        case ExternalRefBinding(ref=ref):
            return {"kind": "External", "scheme": ref.scheme, "value": ref.value}
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(binding)


def deserialize_binding(payload: dict[str, Any]) -> ClearanceBinding:
    """Decode a JSON-friendly dict to a typed ClearanceBinding.

    Dispatches on `payload["kind"]`; raises ValueError on any
    discriminator-or-inner-field violation so a contaminated event
    payload fails loud (KeyError + TypeError are wrapped to ValueError
    so callers don't see leaked low-level exceptions).
    """

    def _build() -> ClearanceBinding:
        kind = payload["kind"]
        match kind:
            case "Subject":
                return SubjectBinding(subject_id=UUID(payload["id"]))
            case "Asset":
                return AssetBinding(asset_id=UUID(payload["id"]))
            case "Run":
                return RunBinding(run_id=UUID(payload["id"]))
            case "Procedure":
                return ProcedureBinding(procedure_id=UUID(payload["id"]))
            case "External":
                return ExternalRefBinding(
                    ref=Identifier(scheme=payload["scheme"], value=payload["value"]),
                )
            case _:
                msg = f"Unknown ClearanceBinding kind: {kind!r}"
                raise ValueError(msg)

    return deserialize_vo_or_raise("ClearanceBinding", _build)


def serialize_classification(c: HazardClassification) -> dict[str, Any]:
    """Encode a typed HazardClassification to a JSON-friendly dict.

    Discriminator `"kind"` selects the arm:
      - `NFPA704`  -- carries health/flammability/instability/special
      - `RiskBand` -- carries band string
      - `GHS`      -- carries pictogram code + sorted statement_codes list
      - `Scheme`   -- carries scheme/code/severity_label
    """
    match c:
        case NFPA704Rating(
            health=health,
            flammability=flammability,
            instability=instability,
            special=special,
        ):
            return {
                "kind": "NFPA704",
                "health": health,
                "flammability": flammability,
                "instability": instability,
                "special": special,
            }
        case RiskBand():
            return {"kind": "RiskBand", "band": c.value}
        case GHSPictogram(code=code, statement_codes=statement_codes):
            return {
                "kind": "GHS",
                "code": code,
                "statement_codes": sorted(statement_codes),
            }
        case SchemeCode(scheme=scheme, code=code, severity_label=severity_label):
            return {
                "kind": "Scheme",
                "scheme": scheme,
                "code": code,
                "severity_label": severity_label,
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(c)


def deserialize_classification(payload: dict[str, Any]) -> HazardClassification:
    """Decode a JSON-friendly dict to a typed HazardClassification.

    Same defensive contract as `deserialize_binding`: any inner-field
    access failure (missing key, wrong type, invalid enum value, etc.)
    is re-raised as ValueError so a contaminated stream fails loud.
    """

    def _build() -> HazardClassification:
        kind = payload["kind"]
        match kind:
            case "NFPA704":
                return NFPA704Rating(
                    health=payload["health"],
                    flammability=payload["flammability"],
                    instability=payload["instability"],
                    special=payload.get("special"),
                )
            case "RiskBand":
                return RiskBand(payload["band"])
            case "GHS":
                return GHSPictogram(
                    code=payload["code"],
                    statement_codes=frozenset(payload.get("statement_codes", [])),
                )
            case "Scheme":
                return SchemeCode(
                    scheme=payload["scheme"],
                    code=payload["code"],
                    severity_label=payload.get("severity_label", ""),
                )
            case _:
                msg = f"Unknown HazardClassification kind: {kind!r}"
                raise ValueError(msg)

    return deserialize_vo_or_raise("HazardClassification", _build)


def serialize_declaration(d: HazardDeclaration) -> dict[str, Any]:
    """Encode a HazardDeclaration to a JSON-friendly dict."""
    return {
        "target": serialize_binding(d.target),
        "classifications": [serialize_classification(c) for c in d.classifications],
        "mitigations": sorted(d.mitigations),
        "notes": d.notes,
    }


def deserialize_declaration(payload: dict[str, Any]) -> HazardDeclaration:
    """Decode a JSON-friendly dict to a HazardDeclaration.

    Defensive: KeyError / TypeError on inner fields are wrapped to
    ValueError so a contaminated stream fails loud at the evolver.
    """
    return deserialize_vo_or_raise(
        "HazardDeclaration",
        lambda: HazardDeclaration(
            target=deserialize_binding(payload["target"]),
            classifications=frozenset(
                deserialize_classification(c) for c in payload.get("classifications", [])
            ),
            mitigations=frozenset(payload.get("mitigations", [])),
            notes=payload.get("notes"),
        ),
    )


def to_payload(event: ClearanceEvent) -> dict[str, Any]:
    """Serialize a Clearance event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, frozensets/tuples become lists. Enum values travel as
    their string values.
    """
    match event:
        case ClearanceRegistered(
            clearance_id=clearance_id,
            kind=kind,
            facility_asset_id=facility_asset_id,
            title=title,
            bindings=bindings,
            declarations=declarations,
            risk_band=risk_band,
            external_id=external_id,
            valid_from=valid_from,
            valid_until=valid_until,
            parent_id=parent_id,
            occurred_at=occurred_at,
        ):
            return {
                "clearance_id": str(clearance_id),
                "kind": kind,
                "facility_asset_id": str(facility_asset_id),
                "title": title,
                "bindings": list(bindings),
                "declarations": list(declarations),
                "risk_band": risk_band,
                "external_id": external_id,
                "valid_from": valid_from.isoformat() if valid_from is not None else None,
                "valid_until": valid_until.isoformat() if valid_until is not None else None,
                "parent_id": (str(parent_id) if parent_id is not None else None),
                "occurred_at": occurred_at.isoformat(),
            }
        case ClearanceSubmitted(clearance_id=cid, occurred_at=occurred_at):
            return {
                "clearance_id": str(cid),
                "occurred_at": occurred_at.isoformat(),
            }
        case ClearanceReviewStarted(
            clearance_id=cid, first_reviewer_role=role, occurred_at=occurred_at
        ):
            return {
                "clearance_id": str(cid),
                "first_reviewer_role": role,
                "occurred_at": occurred_at.isoformat(),
            }
        case ClearanceReviewStepAppended(
            clearance_id=cid,
            step_index=step_index,
            role=role,
            decided_by=decided_by,
            decision=decision,
            decided_at=decided_at,
            notes=notes,
            occurred_at=occurred_at,
        ):
            return {
                "clearance_id": str(cid),
                "step_index": step_index,
                "role": role,
                "decided_by": str(decided_by),
                "decision": decision,
                "decided_at": decided_at.isoformat(),
                "notes": notes,
                "occurred_at": occurred_at.isoformat(),
            }
        case ClearanceApproved(
            clearance_id=cid,
            valid_from=valid_from,
            valid_until=valid_until,
            occurred_at=occurred_at,
        ):
            return {
                "clearance_id": str(cid),
                "valid_from": valid_from.isoformat() if valid_from is not None else None,
                "valid_until": valid_until.isoformat() if valid_until is not None else None,
                "occurred_at": occurred_at.isoformat(),
            }
        case ClearanceRejected(
            clearance_id=cid,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "clearance_id": str(cid),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case ClearanceActivated(clearance_id=cid, occurred_at=occurred_at):
            return {
                "clearance_id": str(cid),
                "occurred_at": occurred_at.isoformat(),
            }
        case ClearanceExpired(
            clearance_id=cid,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "clearance_id": str(cid),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case ClearanceSuperseded(
            clearance_id=cid,
            by_clearance_id=by_cid,
            occurred_at=occurred_at,
        ):
            return {
                "clearance_id": str(cid),
                "by_clearance_id": str(by_cid),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ClearanceEvent:
    """Rebuild a Clearance event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "ClearanceRegistered":

            def _build_registered() -> ClearanceRegistered:
                raw_valid_from = payload.get("valid_from")
                raw_valid_until = payload.get("valid_until")
                raw_parent = payload.get("parent_id")
                return ClearanceRegistered(
                    clearance_id=UUID(payload["clearance_id"]),
                    kind=payload["kind"],
                    facility_asset_id=UUID(payload["facility_asset_id"]),
                    title=payload["title"],
                    bindings=tuple(payload.get("bindings", [])),
                    declarations=tuple(payload.get("declarations", [])),
                    risk_band=payload.get("risk_band"),
                    external_id=payload.get("external_id"),
                    valid_from=(
                        datetime.fromisoformat(raw_valid_from)
                        if raw_valid_from is not None
                        else None
                    ),
                    valid_until=(
                        datetime.fromisoformat(raw_valid_until)
                        if raw_valid_until is not None
                        else None
                    ),
                    parent_id=(UUID(raw_parent) if raw_parent is not None else None),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("ClearanceRegistered", _build_registered)
        case "ClearanceSubmitted":
            return deserialize_or_raise(
                "ClearanceSubmitted",
                lambda: ClearanceSubmitted(
                    clearance_id=UUID(payload["clearance_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ClearanceReviewStarted":
            return deserialize_or_raise(
                "ClearanceReviewStarted",
                lambda: ClearanceReviewStarted(
                    clearance_id=UUID(payload["clearance_id"]),
                    first_reviewer_role=payload["first_reviewer_role"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ClearanceReviewStepAppended":
            return deserialize_or_raise(
                "ClearanceReviewStepAppended",
                lambda: ClearanceReviewStepAppended(
                    clearance_id=UUID(payload["clearance_id"]),
                    step_index=payload["step_index"],
                    role=payload["role"],
                    decided_by=ActorId(UUID(payload["decided_by"])),
                    decision=payload["decision"],
                    decided_at=datetime.fromisoformat(payload["decided_at"]),
                    notes=payload.get("notes"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ClearanceApproved":

            def _build_approved() -> ClearanceApproved:
                raw_valid_from = payload.get("valid_from")
                raw_valid_until = payload.get("valid_until")
                return ClearanceApproved(
                    clearance_id=UUID(payload["clearance_id"]),
                    valid_from=(
                        datetime.fromisoformat(raw_valid_from)
                        if raw_valid_from is not None
                        else None
                    ),
                    valid_until=(
                        datetime.fromisoformat(raw_valid_until)
                        if raw_valid_until is not None
                        else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("ClearanceApproved", _build_approved)
        case "ClearanceRejected":
            return deserialize_or_raise(
                "ClearanceRejected",
                lambda: ClearanceRejected(
                    clearance_id=UUID(payload["clearance_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ClearanceActivated":
            return deserialize_or_raise(
                "ClearanceActivated",
                lambda: ClearanceActivated(
                    clearance_id=UUID(payload["clearance_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ClearanceExpired":
            return deserialize_or_raise(
                "ClearanceExpired",
                lambda: ClearanceExpired(
                    clearance_id=UUID(payload["clearance_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ClearanceSuperseded":
            return deserialize_or_raise(
                "ClearanceSuperseded",
                lambda: ClearanceSuperseded(
                    clearance_id=UUID(payload["clearance_id"]),
                    by_clearance_id=UUID(payload["by_clearance_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown ClearanceEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ClearanceActivated",
    "ClearanceApproved",
    "ClearanceEvent",
    "ClearanceExpired",
    "ClearanceRegistered",
    "ClearanceRejected",
    "ClearanceReviewStarted",
    "ClearanceReviewStepAppended",
    "ClearanceSubmitted",
    "ClearanceSuperseded",
    "deserialize_binding",
    "deserialize_classification",
    "deserialize_declaration",
    "event_type_name",
    "from_stored",
    "serialize_binding",
    "serialize_classification",
    "serialize_declaration",
    "to_payload",
]
