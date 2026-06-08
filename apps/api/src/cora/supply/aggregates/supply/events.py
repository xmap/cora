"""Domain events emitted by the Supply aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

`SupplyRegistered` is the genesis (-> Unknown);
`SupplyMarkedAvailable` covers the first-observation transition
(Unknown -> Available); `SupplyDegraded`, `SupplyMarkedUnavailable`,
`SupplyMarkedRecovering`, and `SupplyRestored` cover the full
degradation/recovery cycle. `SupplyDeregistered` is the lifecycle-
terminal transition (any non-Decommissioned -> Decommissioned). All
6 transition events share the same payload shape (`from_status,
reason, trigger, triggered_by, occurred_at`) so the projection can
fold them through one parameterized UPDATE.

Status is NOT carried in `SupplyRegistered`'s payload — the event
type IS the state-change indicator (matches `FamilyDefined ->
DEFINED`, `SubjectMounted -> MOUNTED`). Status DOES travel in
transition-event payloads as `from_status` so the projection can
reconstruct exact source-state audit without re-folding the prior
stream.

`scope` and `kind` travel in the genesis payload as primitive strings;
the evolver reconstructs typed `SupplyScope` and `SupplyKind` VOs.
Same precedent as `AssetLevel` in payloads.

`trigger` travels in every event payload as a `TriggerSource` enum
string. Locked 3-value day one (`Operator | Monitor | Auto`) even
though only `Operator` and `Monitor` are wired today. Forward-compat
motivation in [[project_supply_design]].

`triggered_by` travels alongside `trigger` as a UUID-shaped attribution
field whose typed identity tier is pinned by the trigger string:

  - trigger="Operator" -> triggered_by is an `ActorId`
  - trigger="Monitor"  -> triggered_by is a `MonitorSourceId`
  - trigger="Auto"     -> triggered_by is a `SchedulerTickId`

The trigger/triggered_by pairing is the cross-tier attribution
discipline locked by [[project_fold_symmetry_design]]: every
transversal-time fold (`occurred_at`) is paired with a transversal-
attribution counterpart (`triggered_by`). Per the design memo,
Supply stays fold-NEITHER on aggregate state; the pair lives on the
event payload only. The pairing invariant is enforced in
`__post_init__` of each event class to catch malformed constructions
at event-creation time rather than at projection-read time.

`reason` travels in transition-event payloads as a primitive string
(validated and trimmed via `SupplyReason` VO at the decider; payload
carries the trimmed value). Same precedent as `AssetRelocated.reason`
+ `RunAborted.reason`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId, MonitorSourceId, SchedulerTickId

# Trigger-aware discriminated union for the `triggered_by` attribution
# field. NewType-based; pyright treats the three options as distinct at
# type-check time so a slice mis-using the wrong identity tier fails to
# compile.
TriggeredBy = ActorId | MonitorSourceId | SchedulerTickId


def _check_trigger_pairing(trigger: str, triggered_by: UUID) -> None:
    """Enforce the trigger -> triggered_by-type pairing at event construction.

    Per [[project_fold_symmetry_design]]: trigger="Operator" pairs
    with an `ActorId`, trigger="Monitor" with a `MonitorSourceId`,
    trigger="Auto" with a `SchedulerTickId`. NewType is erased at
    runtime so the type-distinction enforcement happens at static
    analysis (pyright). The runtime invariant we CAN enforce is the
    UUID-shape of the field plus the trigger-string being a known
    discriminator value; the static type system rejects passing the
    wrong NewType at every construction site.
    """
    if not isinstance(triggered_by, UUID):  # pyright: ignore[reportUnnecessaryIsInstance]
        msg = (
            f"triggered_by must be a UUID-shaped identity (got "
            f"{type(triggered_by).__name__}); pair trigger={trigger!r} "
            f"with the matching identity tier."
        )
        raise TypeError(msg)
    if trigger not in {"Operator", "Monitor", "Auto"}:
        msg = (
            f"trigger must be one of Operator / Monitor / Auto "
            f"(got {trigger!r}); see TriggerSource."
        )
        raise ValueError(msg)


@dataclass(frozen=True)
class SupplyRegistered:
    """A new continuously-available resource was registered.

    Status is implicit (`Unknown`) — the evolver sets it. Per the
    universal initial-state convention (Tango UNKNOWN, EPICS UDF,
    Azure Resource Health Unknown, k8s Pending), a newly-registered
    Supply has not yet been observed and therefore has no asserted
    availability state.

    Registration is always operator-driven (no Monitor or Auto
    counterpart); `trigger` is always "Operator" and `triggered_by`
    is always an `ActorId`. The pair is folded onto the event
    payload for cross-tier attribution symmetry per
    [[project_fold_symmetry_design]].
    """

    supply_id: UUID
    scope: str
    kind: str
    name: str
    trigger: str
    triggered_by: TriggeredBy
    occurred_at: datetime

    def __post_init__(self) -> None:
        _check_trigger_pairing(self.trigger, self.triggered_by)


@dataclass(frozen=True)
class SupplyMarkedAvailable:
    """An operator declared the Supply Available for the first time.

    Single-source transition: `Unknown -> Available`. Distinct from
    `SupplyRestored` (`Recovering -> Available`, recovery
    acknowledgement) per the Phoebus latched-alarm precedent: first-
    observation declaration and recovery-confirmation are two
    different operator gestures even though they target the same
    `Available` status.

    `from_status` is always `Unknown` for this initial transition;
    carried in the payload anyway for projection-update simplicity
    and audit clarity (matches the other transition events' shape).

    `reason` is a free-form short string explaining the operator's
    declaration ("operator confirms LN2 supply is up after morning
    walkdown"). Validated 1-500 chars in the decider via
    `SupplyReason` VO.

    `trigger` is the locked 3-value `TriggerSource` enum, always
    `Operator` today (substream-driven `Monitor` and timer-driven
    `Auto` are deferred-with-trigger). `triggered_by` is the typed
    attribution UUID whose tier (Actor / Monitor / Scheduler) is
    pinned by `trigger` per [[project_fold_symmetry_design]].
    """

    supply_id: UUID
    from_status: str
    reason: str
    trigger: str
    triggered_by: TriggeredBy
    occurred_at: datetime
    monitor_ref: str | None = None

    def __post_init__(self) -> None:
        _check_trigger_pairing(self.trigger, self.triggered_by)


@dataclass(frozen=True)
class SupplyDegraded:
    """The Supply transitioned to Degraded (10a-b).

    Multi-source: `{Unknown, Available, Recovering} -> Degraded`. The
    resource is up but below nominal capacity / quality (for example,
    photon beam at half-current after partial top-up; LN2 dewar at
    20% pressure margin). Same payload shape as
    `SupplyMarkedAvailable`.
    """

    supply_id: UUID
    from_status: str
    reason: str
    trigger: str
    triggered_by: TriggeredBy
    occurred_at: datetime
    monitor_ref: str | None = None

    def __post_init__(self) -> None:
        _check_trigger_pairing(self.trigger, self.triggered_by)


@dataclass(frozen=True)
class SupplyMarkedUnavailable:
    """The Supply transitioned to Unavailable (10a-b).

    Widest source set: `{Unknown, Available, Degraded, Recovering} ->
    Unavailable`. The resource is down (planned shutdown, beam dump,
    LN2 empty, vacuum loss). Same payload shape as
    `SupplyMarkedAvailable`.
    """

    supply_id: UUID
    from_status: str
    reason: str
    trigger: str
    triggered_by: TriggeredBy
    occurred_at: datetime
    monitor_ref: str | None = None

    def __post_init__(self) -> None:
        _check_trigger_pairing(self.trigger, self.triggered_by)


@dataclass(frozen=True)
class SupplyMarkedRecovering:
    """The Supply transitioned to Recovering (10a-b).

    Single-source: `{Unavailable} -> Recovering`. Observation
    suggests the underlying resource may be coming back; the
    operator hasn't yet confirmed full availability. Per the Phoebus
    latched-alarm pattern, `Recovering -> Available` requires an
    explicit `restore_supply` (operator acknowledgement); this event
    is the entry into that latched state. Same payload shape as
    `SupplyMarkedAvailable`.
    """

    supply_id: UUID
    from_status: str
    reason: str
    trigger: str
    triggered_by: TriggeredBy
    occurred_at: datetime
    monitor_ref: str | None = None

    def __post_init__(self) -> None:
        _check_trigger_pairing(self.trigger, self.triggered_by)


@dataclass(frozen=True)
class SupplyRestored:
    """The Supply transitioned from Recovering back to Available (10a-b).

    Single-source: `{Recovering} -> Available`. This is the
    recovery-acknowledgement event, distinct from
    `SupplyMarkedAvailable` (first-observation declaration). Per the
    Phoebus latched-alarm and PackML CLEARING -> RESETTING -> IDLE
    convention, explicit operator gesture is required (auto-timer-
    confirmed restore is deferred-with-trigger per Watch item 1 in
    [[project_supply_design]]).

    Same payload shape as `SupplyMarkedAvailable`.
    """

    supply_id: UUID
    from_status: str
    reason: str
    trigger: str
    triggered_by: TriggeredBy
    occurred_at: datetime
    monitor_ref: str | None = None

    def __post_init__(self) -> None:
        _check_trigger_pairing(self.trigger, self.triggered_by)


@dataclass(frozen=True)
class SupplyDeregistered:
    """The Supply was deregistered; transitions to terminal Decommissioned.

    Widest source set of any Supply transition: any non-Decommissioned
    status. Lifecycle terminal (no transition exits Decommissioned;
    re-registration creates a fresh `supply_id`). `from_status`
    captures whichever health state the Supply held immediately before
    deregistration, preserved on the event log for audit. Same payload
    shape as the other five transition events.

    Per [[project_deregister_supply_design]], this is the operator
    escape hatch for mistaken registrations. The trigger is always
    `Operator`; substream and timer auto-decommission are not modeled.
    """

    supply_id: UUID
    from_status: str
    reason: str
    trigger: str
    triggered_by: TriggeredBy
    occurred_at: datetime
    monitor_ref: str | None = None

    def __post_init__(self) -> None:
        _check_trigger_pairing(self.trigger, self.triggered_by)


# Discriminated union of every event the Supply aggregate emits.
SupplyEvent = (
    SupplyRegistered
    | SupplyMarkedAvailable
    | SupplyDegraded
    | SupplyMarkedUnavailable
    | SupplyMarkedRecovering
    | SupplyRestored
    | SupplyDeregistered
)


def event_type_name(event: SupplyEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: SupplyEvent) -> dict[str, Any]:
    """Serialize a Supply event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings. Enum values travel as their string values (already
    str-typed via StrEnum but cast here for explicitness).
    """
    match event:
        case SupplyRegistered(
            supply_id=supply_id,
            scope=scope,
            kind=kind,
            name=name,
            trigger=trigger,
            triggered_by=triggered_by,
            occurred_at=occurred_at,
        ):
            return {
                "supply_id": str(supply_id),
                "scope": scope,
                "kind": kind,
                "name": name,
                "trigger": trigger,
                "triggered_by": str(triggered_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case (
            SupplyMarkedAvailable(
                supply_id=supply_id,
                from_status=from_status,
                reason=reason,
                trigger=trigger,
                triggered_by=triggered_by,
                occurred_at=occurred_at,
                monitor_ref=monitor_ref,
            )
            | SupplyDegraded(
                supply_id=supply_id,
                from_status=from_status,
                reason=reason,
                trigger=trigger,
                triggered_by=triggered_by,
                occurred_at=occurred_at,
                monitor_ref=monitor_ref,
            )
            | SupplyMarkedUnavailable(
                supply_id=supply_id,
                from_status=from_status,
                reason=reason,
                trigger=trigger,
                triggered_by=triggered_by,
                occurred_at=occurred_at,
                monitor_ref=monitor_ref,
            )
            | SupplyMarkedRecovering(
                supply_id=supply_id,
                from_status=from_status,
                reason=reason,
                trigger=trigger,
                triggered_by=triggered_by,
                occurred_at=occurred_at,
                monitor_ref=monitor_ref,
            )
            | SupplyRestored(
                supply_id=supply_id,
                from_status=from_status,
                reason=reason,
                trigger=trigger,
                triggered_by=triggered_by,
                occurred_at=occurred_at,
                monitor_ref=monitor_ref,
            )
            | SupplyDeregistered(
                supply_id=supply_id,
                from_status=from_status,
                reason=reason,
                trigger=trigger,
                triggered_by=triggered_by,
                occurred_at=occurred_at,
                monitor_ref=monitor_ref,
            )
        ):
            payload: dict[str, Any] = {
                "supply_id": str(supply_id),
                "from_status": from_status,
                "reason": reason,
                "trigger": trigger,
                "triggered_by": str(triggered_by),
                "occurred_at": occurred_at.isoformat(),
            }
            if monitor_ref is not None:
                payload["monitor_ref"] = monitor_ref
            return payload
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _typed_triggered_by(trigger: str, raw_uuid: UUID) -> TriggeredBy:
    """Re-wrap the bare UUID in the NewType implied by the trigger string.

    NewType is erased at runtime (the wrappers are identity functions
    returning the same UUID), but calling them here makes the typing
    intent explicit at the deserialization boundary and gives pyright
    a load-bearing signal for downstream consumers of `from_stored`.
    """
    if trigger == "Operator":
        return ActorId(raw_uuid)
    if trigger == "Monitor":
        return MonitorSourceId(raw_uuid)
    if trigger == "Auto":
        return SchedulerTickId(raw_uuid)
    msg = (
        f"Cannot deserialize triggered_by: unknown trigger {trigger!r}; "
        f"expected one of Operator / Monitor / Auto."
    )
    raise ValueError(msg)


def from_stored(stored: StoredEvent) -> SupplyEvent:
    """Rebuild a Supply event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "SupplyRegistered":
            return deserialize_or_raise(
                "SupplyRegistered",
                lambda: SupplyRegistered(
                    supply_id=UUID(payload["supply_id"]),
                    scope=payload["scope"],
                    kind=payload["kind"],
                    name=payload["name"],
                    trigger=payload["trigger"],
                    triggered_by=_typed_triggered_by(
                        payload["trigger"], UUID(payload["triggered_by"])
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "SupplyMarkedAvailable":
            return deserialize_or_raise(
                "SupplyMarkedAvailable",
                lambda: SupplyMarkedAvailable(**_transition_kwargs(payload)),
            )
        case "SupplyDegraded":
            return deserialize_or_raise(
                "SupplyDegraded",
                lambda: SupplyDegraded(**_transition_kwargs(payload)),
            )
        case "SupplyMarkedUnavailable":
            return deserialize_or_raise(
                "SupplyMarkedUnavailable",
                lambda: SupplyMarkedUnavailable(**_transition_kwargs(payload)),
            )
        case "SupplyMarkedRecovering":
            return deserialize_or_raise(
                "SupplyMarkedRecovering",
                lambda: SupplyMarkedRecovering(**_transition_kwargs(payload)),
            )
        case "SupplyRestored":
            return deserialize_or_raise(
                "SupplyRestored",
                lambda: SupplyRestored(**_transition_kwargs(payload)),
            )
        case "SupplyDeregistered":
            return deserialize_or_raise(
                "SupplyDeregistered",
                lambda: SupplyDeregistered(**_transition_kwargs(payload)),
            )
        case _:
            msg = f"Unknown SupplyEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


def _transition_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """Shared payload-deserialization for all 6 transition events.

    All transitions (SupplyMarkedAvailable / SupplyDegraded /
    SupplyMarkedUnavailable / SupplyMarkedRecovering / SupplyRestored
    / SupplyDeregistered) carry the same `(supply_id, from_status,
    reason, trigger, triggered_by, occurred_at, monitor_ref)` shape.
    Hoisting this kwargs builder keeps each `from_stored` arm one-line
    and avoids 6 copies of the same dict literal.
    """
    trigger = payload["trigger"]
    return {
        "supply_id": UUID(payload["supply_id"]),
        "from_status": payload["from_status"],
        "reason": payload["reason"],
        "trigger": trigger,
        "triggered_by": _typed_triggered_by(trigger, UUID(payload["triggered_by"])),
        "occurred_at": datetime.fromisoformat(payload["occurred_at"]),
        "monitor_ref": payload.get("monitor_ref"),
    }


__all__ = [
    "SupplyDegraded",
    "SupplyDeregistered",
    "SupplyEvent",
    "SupplyMarkedAvailable",
    "SupplyMarkedRecovering",
    "SupplyMarkedUnavailable",
    "SupplyRegistered",
    "SupplyRestored",
    "TriggeredBy",
    "event_type_name",
    "from_stored",
    "to_payload",
]
