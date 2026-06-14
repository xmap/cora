"""Domain events emitted by the Enclosure aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

`EnclosureRegistered` is the genesis (-> Unknown permit-status, Active
lifecycle). It carries the containing-geography anchor `facility_code`
(the Federation Facility the enclosure sits within) as a bare-str disk
payload re-wrapped to the typed `FacilityCode` VO by `from_stored`,
mirroring the Supply / Asset facility-code wire convention.
`EnclosurePermitObserved` is the sole permit-axis
transition (any -> any across the closed `Permitted | NotPermitted |
Unknown` state set). `EnclosureDecommissioned` is the lifecycle-
terminal transition (Active -> Decommissioned). Permit-status is
preserved untouched across decommission as audit trail; the two axes
are orthogonal per [[project_enclosure_stage1_design]] (D6.L2
observation-axis-only, D10-L1 no Bypassed state).

Permit-status is NOT carried in `EnclosureRegistered`'s payload; the
evolver seeds it to `Unknown` per the universal initial-state
convention (Tango UNKNOWN, EPICS UDF, Azure Resource Health Unknown,
k8s Pending). The `EnclosurePermitObserved` payload carries BOTH
`from_status` and `to_status` so the projection can reconstruct exact
source-state audit without re-folding the prior stream and so the
evolver can fold the new status directly from the event.

`EnclosureRegistered` and `EnclosureDecommissioned` are operator-only
today; `triggered_by` (and `registered_by` on the genesis) is
typed `ActorId` directly, not the trigger-aware union. The trigger
discriminator is implicit (operator) and is not carried on the
payload. Widening to Monitor / Auto registration is deferred-with-
trigger per the locked design.

`EnclosurePermitObserved` is Monitor-only per the D6.L2
anti-lock (observation-axis only, no operator-asserted permit
state); `triggered_by` is typed `MonitorSourceId` directly, not the
trigger-aware union. The `trigger` field is carried on the payload
anyway so the projection schema and
arch fitness checks stay aligned with the Supply precedent and so
the future widening to operator-asserted overrides is purely
additive. `monitor_ref` is required-when-trigger-is-Monitor and
carries the substream attribution as '{source_kind}:{source_id}';
omit-when-None on the wire keeps the convention with Supply's six
transition events even though always populates it.

`reason` travels on every transition payload as a primitive string
(validated and trimmed via `EnclosureReason` VO at the decider;
payload carries the trimmed value). Same precedent as
`SupplyReason`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId, MonitorSourceId


def _check_trigger_pairing(
    trigger: str,
    triggered_by: UUID,
    monitor_ref: str | None,
) -> None:
    """Enforce the trigger -> triggered_by + monitor_ref invariant.

    The locked design constrains `EnclosurePermitObserved` to Monitor-only per the
    D6.L2 observation-axis-only anti-lock; `triggered_by` must be a
    `MonitorSourceId` and `monitor_ref` must be populated. NewType is
    erased at runtime so the type-distinction enforcement happens at
    static analysis (pyright). The runtime invariants we CAN enforce
    are the UUID-shape of the attribution field, the trigger-string
    being the locked value, and the monitor_ref pairing
    discipline; the static type system rejects passing the wrong
    NewType at every construction site.
    """
    if not isinstance(triggered_by, UUID):  # pyright: ignore[reportUnnecessaryIsInstance]
        msg = (
            f"triggered_by must be a UUID-shaped identity (got "
            f"{type(triggered_by).__name__}); pair trigger={trigger!r} "
            f"with the matching identity tier."
        )
        raise TypeError(msg)
    if trigger != "Monitor":
        msg = (
            f"trigger must be 'Monitor' (got {trigger!r}); "
            f"operator-asserted permit overrides are deferred-with-trigger "
            f"per the D6.L2 observation-axis-only anti-lock."
        )
        raise ValueError(msg)
    if monitor_ref is None:
        msg = (
            f"monitor_ref is required when trigger={trigger!r}; "
            f"populate '{{source_kind}}:{{source_id}}' to attribute the "
            f"observation to a specific substream."
        )
        raise ValueError(msg)


@dataclass(frozen=True)
class EnclosureRegistered:
    """A new enclosure was registered within its containing Facility.

    Permit-status is implicit (`Unknown`) and lifecycle is implicit
    (`Active`); the evolver sets both. Per the universal initial-
    state convention (Tango UNKNOWN, EPICS UDF, Azure Resource Health
    Unknown, k8s Pending), a newly-registered Enclosure has not yet
    been observed and therefore has no asserted permit state.

    Registration is operator-only today (no Monitor or Auto
    counterpart); `registered_by` is typed `ActorId` directly. The
    `(registered_at=occurred_at, registered_by)` pair is the fold-
    symmetric genesis attribution per [[project_fold_symmetry_design]];
    the evolver folds both onto aggregate state.

    `name` travels in the genesis payload as a primitive string; the
    evolver re-wraps to the `EnclosureName` VO. Same precedent as
    `SupplyName` / `FacilityName` in payloads.

    `facility_code` is the containing geography (the Site / Area the
    enclosure sits within); it carries the typed `FacilityCode` VO in
    memory and serializes to a bare `str` on the wire via
    `facility_code.value`, mirroring the Supply / Asset facility-code
    convention. `from_stored` re-wraps with `FacilityCode(...)`.
    """

    enclosure_id: UUID
    name: str
    facility_code: FacilityCode
    registered_by: ActorId
    occurred_at: datetime


@dataclass(frozen=True)
class EnclosurePermitObserved:
    """A substream observed the enclosure's permit status (any -> any).

    Sole permit-axis transition today. Source set is the full
    closed `EnclosurePermitStatus` set (`Permitted | NotPermitted |
    Unknown`); target set is the same. `from_status` and `to_status`
    both travel in the payload so the projection can update without
    re-folding the prior stream and so the evolver can fold the new
    status directly.

    `trigger` is locked to `Monitor` today per the D6.L2 anti-
    lock (observation-axis-only; operator-asserted overrides are
    deferred-with-trigger). `triggered_by` is typed `MonitorSourceId`
    directly, not the trigger-aware union. `monitor_ref` is required-
    when-trigger-is-Monitor and carries '{source_kind}:{source_id}'
    substream attribution; omit-when-None on the wire keeps the
    convention with Supply's transition events.

    `reason` is a free-form short string explaining the observation
    ('PSS interlock chain healthy', 'EPS shutter closed pending
    survey'). Validated 1-500 chars in the decider via
    `EnclosureReason` VO.
    """

    enclosure_id: UUID
    from_status: str
    to_status: str
    reason: str
    trigger: str
    triggered_by: MonitorSourceId
    occurred_at: datetime
    monitor_ref: str | None = None

    def __post_init__(self) -> None:
        _check_trigger_pairing(self.trigger, self.triggered_by, self.monitor_ref)


@dataclass(frozen=True)
class EnclosureDecommissioned:
    """The enclosure was decommissioned; transitions to terminal Decommissioned.

    Sole lifecycle-axis transition: `Active -> Decommissioned`.
    Terminal (no transition exits Decommissioned; re-commissioning
    creates a fresh `enclosure_id`). Permit-status is preserved
    untouched across decommission as audit trail per the orthogonality
    note in [[project_enclosure_stage1_design]].

    Operator-only today; `triggered_by` is typed `ActorId`
    directly, not the trigger-aware union. The
    `(decommissioned_at=occurred_at, decommissioned_by=triggered_by)`
    pair is the fold-symmetric terminal attribution per
    [[project_fold_symmetry_design]]; the evolver folds both onto
    aggregate state.

    `reason` is a free-form short string explaining the
    decommissioning ('enclosure consolidated into adjacent hutch',
    'instrument removed and Asset retired'). Validated 1-500 chars
    in the decider via `EnclosureReason` VO.
    """

    enclosure_id: UUID
    reason: str
    triggered_by: ActorId
    occurred_at: datetime


# Discriminated union of every event the Enclosure aggregate emits.
EnclosureEvent = EnclosureRegistered | EnclosurePermitObserved | EnclosureDecommissioned


def event_type_name(event: EnclosureEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: EnclosureEvent) -> dict[str, Any]:
    """Serialize an Enclosure event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings. `monitor_ref` is omitted when None per the wire
    convention shared with Supply's transition events.
    """
    match event:
        case EnclosureRegistered(
            enclosure_id=enclosure_id,
            name=name,
            facility_code=facility_code,
            registered_by=registered_by,
            occurred_at=occurred_at,
        ):
            return {
                "enclosure_id": str(enclosure_id),
                "name": name,
                "facility_code": facility_code.value,
                "registered_by": str(registered_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case EnclosurePermitObserved(
            enclosure_id=enclosure_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            trigger=trigger,
            triggered_by=triggered_by,
            occurred_at=occurred_at,
            monitor_ref=monitor_ref,
        ):
            payload: dict[str, Any] = {
                "enclosure_id": str(enclosure_id),
                "from_status": from_status,
                "to_status": to_status,
                "reason": reason,
                "trigger": trigger,
                "triggered_by": str(triggered_by),
                "occurred_at": occurred_at.isoformat(),
            }
            if monitor_ref is not None:
                payload["monitor_ref"] = monitor_ref
            return payload
        case EnclosureDecommissioned(
            enclosure_id=enclosure_id,
            reason=reason,
            triggered_by=triggered_by,
            occurred_at=occurred_at,
        ):
            return {
                "enclosure_id": str(enclosure_id),
                "reason": reason,
                "triggered_by": str(triggered_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> EnclosureEvent:
    """Rebuild an Enclosure event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "EnclosureRegistered":
            return deserialize_or_raise(
                "EnclosureRegistered",
                lambda: EnclosureRegistered(
                    enclosure_id=UUID(payload["enclosure_id"]),
                    name=payload["name"],
                    facility_code=FacilityCode(payload["facility_code"]),
                    registered_by=ActorId(UUID(payload["registered_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case "EnclosurePermitObserved":
            return deserialize_or_raise(
                "EnclosurePermitObserved",
                lambda: EnclosurePermitObserved(
                    enclosure_id=UUID(payload["enclosure_id"]),
                    from_status=payload["from_status"],
                    to_status=payload["to_status"],
                    reason=payload["reason"],
                    trigger=payload["trigger"],
                    triggered_by=MonitorSourceId(UUID(payload["triggered_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    monitor_ref=payload.get("monitor_ref"),
                ),
                extra=(ValueError,),
            )
        case "EnclosureDecommissioned":
            return deserialize_or_raise(
                "EnclosureDecommissioned",
                lambda: EnclosureDecommissioned(
                    enclosure_id=UUID(payload["enclosure_id"]),
                    reason=payload["reason"],
                    triggered_by=ActorId(UUID(payload["triggered_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case _:
            msg = f"Unknown EnclosureEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "EnclosureDecommissioned",
    "EnclosureEvent",
    "EnclosurePermitObserved",
    "EnclosureRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
