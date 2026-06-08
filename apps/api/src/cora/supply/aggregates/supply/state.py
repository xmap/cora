"""Supply aggregate state, value objects, status enum, and domain errors.

`Supply` is a continuously-available resource that other aggregates
depend on: photon beam, LN2, compressed air, electrical power,
cooling water, vacuum, process gases, compute pool, FEL pulses,
neutrons. Per the BC map, `Supply` is the Track B intro aggregate,
multiple instances at runtime, one per resource. Physical
infrastructure delivering the resource (gas cabinets, compressors,
mass-flow controllers) stays as `Asset`s; the resource itself is
`Supply`.

The aggregate is intentionally slim: identity + scope + kind + name
+ a single `status` field driving the FSM. The 5-state FSM is locked
day one per [[project_supply_design]]:

  Unknown -> Available
  Unknown -> Degraded
  Unknown -> Unavailable
  Available -> Degraded
  Available -> Unavailable
  Degraded -> Available
  Degraded -> Unavailable
  Unavailable -> Recovering
  Recovering -> Available    (operator-ack via restore_supply slice)
  Recovering -> Degraded
  Recovering -> Unavailable

`Unknown` is the registration-time initial state per universal
precedent (Tango UNKNOWN, EPICS UDF/INVALID, areaDetector
ADStatusInitializing, SKA Tango Base INIT, Azure Resource Health
Unknown, Kubernetes Pod Pending, Prometheus `up{}` UNKNOWN-before-
first-scrape, BACnet out_of_service, PackML STOPPED, PI Pt Created).
The optimistic-Available default is an anti-pattern across all three
research corpora.


Minimal Supply: id + scope + kind + name + status (defaults Unknown
implicitly via genesis evolver). 10a-a shipped `register_supply`
(genesis -> Unknown) and `mark_supply_available` (Unknown ->
Available, operator-asserted first observation). 10a-b closed the
FSM with `degrade`, `mark_unavailable`, `mark_recovering`, and
`restore` (the last is the recovery acknowledgement, distinct from
`mark_supply_available`'s first-observation semantics).

## Status as enum-in-state, derived-from-event-type-in-evolver

`SupplyStatus` is a `StrEnum` so the values serialize naturally as
JSON-friendly strings IF carried in an event payload. State holds
the enum (typed); evolver derives status from event type
(`SupplyRegistered -> UNKNOWN`, `SupplyMarkedAvailable -> AVAILABLE`).
Same precedent as `SubjectStatus` / `FamilyStatus` /
`AssetLifecycle`.

`SupplyScope` enum value DOES travel in event payloads (scope is set
at registration and doesn't change). The payload carries the string;
the evolver reconstructs via `SupplyScope(payload["scope"])`. Same
precedent as `AssetLevel`.

## TriggerSource locked 3-value day one

`TriggerSource` is locked at three values (`Operator`, `Monitor`,
`Auto`) from day one even though only `Operator` is used today.
The forward-compat motivation is in [[project_supply_design]]: when
substream-driven `Monitor` slices and timer-based `Auto` recovery
land, the enum doesn't need to widen. Carried in transition-event
payloads as the trigger discriminator.

## Identity: stable opaque + typed address

`Supply` carries `id: UUID` (stable opaque handle, survives any
operator-driven name changes; survives physical equipment swaps once
binding lands per Watch item 6) plus `(scope, kind, name)` typed
address. The 4-tuple `(scope, kind, name)` is the operator-readable
identity surfaced in REST/MCP and indexed in the projection. The
projection-side UNIQUE INDEX on `(scope, kind, name)` catches
duplicate registrations at insert time; aggregates cannot enforce
cross-stream uniqueness without DCB (per [[project_deferred]]).

## Eleventh bounded-name VO

`SupplyName` is the eleventh trimmed-bounded-name VO. Uses the
shared `validate_bounded_text` helper
(`cora.shared.bounded_text`).

## SupplyKind shape, BARE str, not a VO (gate-review lock)

`kind: str` is bare on the Supply state, NOT a VO. Validated at the
decider via `validate_bounded_text` (1-50 chars after trim) and at
the API boundary via Pydantic min_length / max_length. Closed
StrEnum was rejected universally across all three research corpora
(Kubernetes CRD, Crossplane MRD, OpenTelemetry semantic conventions,
CloudEvents reverse-DNS; ISA-95 property model; IEC 61850 namespace
extensions).

The bare-str-not-VO choice was caught by the gate review and
backed by Khononov 2024 *Balancing Coupling*: wrap a primitive in a
VO when the type carries domain *behavior or comparison semantics*,
not when it merely needs a length check. Two converging arguments
for the bare form here:

  1. `kind` will eventually graduate to `SupplyKind: StrEnum` once
     pilot vocabulary settles (Watch item 4 in
     [[project_supply_design]]). Migration `str -> StrEnum` is a
     clean parser change; `SupplyKind(VO) -> SupplyKind(StrEnum)`
     would break every type-annotated call site.
  2. `AssetPort.signal_type: str` is the in-codebase precedent:
     bare-str discriminator with inline-validation, awaiting future
     enum promotion. Same shape applies here.

Documented starter vocabulary lives in [[project_supply_design]] as
guidance, not constraint: PhotonBeam, FELPulses, Neutrons, IonBeam,
LiquidNitrogen, LiquidHelium, CompressedAir, CoolingWater,
ChilledWater, ElectricalPower, ProcessGas, Vacuum, ComputePool.

`SupplyName` and `SupplyReason` STAY as VOs — `SupplyName` is a true
free-form display name (will never be an enum), and `SupplyReason`
is operator-supplied prose (matches `RunAbortReason` /
`RunStopReason` / `RunTruncateReason` precedent exactly).
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.shared.bounded_text import bounded_name, validate_bounded_text
from cora.shared.scope_markers import Annotated, DeferredVocabulary

SUPPLY_NAME_MAX_LENGTH = 200
SUPPLY_KIND_MAX_LENGTH = 50
SUPPLY_REASON_MAX_LENGTH = 500


class SupplyStatus(StrEnum):
    """The Supply's availability state.

    Five health states + one lifecycle terminal per
    [[project_supply_design]] + [[project_deregister_supply_design]]:

      - `Unknown`: registration-time default; no observation yet
      - `Available`: resource is up and meeting consumer needs
      - `Degraded`: resource is up but below nominal capacity / quality
      - `Unavailable`: resource is down (planned or unplanned)
      - `Recovering`: resource was Unavailable; observation suggests
                        it may be coming back; operator must `restore_supply`
                        to confirm `Recovering -> Available`
      - `Decommissioned`: lifecycle terminal; the Supply was deregistered.
                          NOT a health state; a tombstone parallel to
                          `Actor.active=false`, `Subject.status=Discarded`,
                          `Asset.lifecycle=Decommissioned`. No transition exits
                          this state; re-registration creates a fresh `supply_id`.
                          Do NOT interpret this value as license to add `Faulted`,
                          `Maintenance`, or any other health-state widening; those
                          remain fenced by Anti-hook 1 of [[project_supply_design]].

    Naming asymmetry (deliberate): the operator gesture is `deregister_supply`
    (paired with `register_supply` for natural register/deregister UX);
    the event class is `SupplyDeregistered` (matches the gesture); but the
    resulting status value is `DECOMMISSIONED` (matches the cross-BC
    tombstone vocabulary established by `Asset.lifecycle.DECOMMISSIONED`).
    The gesture-vs-status split is intentional: operator-facing surfaces
    speak `register`/`deregister`; event-log + status-projection surfaces
    speak the cross-BC tombstone vocabulary. See
    [[project_deregister_supply_design]].

    Initial `Unknown` is universal industrial + cloud-native consensus
    (Tango UNKNOWN, EPICS UDF, Azure Resource Health Unknown, k8s
    Pending, Prometheus `up{}` UNKNOWN-before-first-scrape). The
    optimistic-Available default is an anti-pattern.
    """

    UNKNOWN = "Unknown"
    AVAILABLE = "Available"
    DEGRADED = "Degraded"
    UNAVAILABLE = "Unavailable"
    RECOVERING = "Recovering"
    DECOMMISSIONED = "Decommissioned"


class SupplyScope(StrEnum):
    """The hierarchical scope at which a Supply is provisioned.

    Three values per APS LMA18-3 LN2 distribution layering and
    NeXus NXsource one-source-per-storage-ring precedent:

      - `Facility`: facility-wide resource (storage-ring photon beam,
        central LN2 plant, building electrical power, central
        compressed air)
      - `Sector`: a sub-portion of the facility (ring sector, gas-
        manifold loop serving N beamlines)
      - `Beamline`: beamline-local resource (per-beamline LN2 drop,
        beamline-local vacuum subsystem, beamline-local compute)

    Adding finer-grained scopes (for example, Substrate, Chamber) is purely
    additive when triggers fire.
    """

    FACILITY = "Facility"
    SECTOR = "Sector"
    BEAMLINE = "Beamline"


class TriggerSource(StrEnum):
    """The origin of a status-transition event.

    Three values locked day one per [[project_supply_design]] for
    forward-compat. Only `Operator` is wired today; `Monitor`
    and `Auto` are reserved for future slice families:

      - `Operator`: explicit operator command
      - `Monitor`: substream-derived observation (deferred; needs
        first DAQ substream ingest, paired with run-reading trigger)
      - `Auto`: timer-based auto-restore (deferred; needs first
        operator complaint about `restore_supply` ack overhead OR
        30+ days of substream-stable recoveries)

    Locking three values day one avoids enum-evolution churn when
    the deferred features land.
    """

    OPERATOR = "Operator"
    MONITOR = "Monitor"
    AUTO = "Auto"


class InvalidSupplyNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Supply name must be 1-{SUPPLY_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidSupplyKindError(ValueError):
    """The supplied kind is empty, whitespace-only, or too long.

    Free-form 1-50 chars today; future promotion to closed StrEnum
    is a watch item per [[project_supply_design]]. Raised by the
    `register_supply` decider via `validate_bounded_text`, NOT by a
    `__post_init__` (kind is a bare `str` on Supply state, not a
    VO; gate-review lock).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Supply kind must be 1-{SUPPLY_KIND_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidSupplyReasonError(ValueError):
    """The supplied transition reason is empty, whitespace-only, or too long.

    Validated at API boundary AND defensively at the decider so
    direct in-process callers (sagas, tests) get the same protection.
    Same precedent as `RunAbortReason`, `PromotionReason`,
    `AssetCondition` reason fields.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Supply transition reason must be 1-{SUPPLY_REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class SupplyAlreadyExistsError(Exception):
    """Attempted to register a supply whose stream already has events."""

    def __init__(self, supply_id: UUID) -> None:
        super().__init__(f"Supply {supply_id} already exists")
        self.supply_id = supply_id


class SupplyNotFoundError(Exception):
    """Attempted an operation on a supply whose stream has no events."""

    def __init__(self, supply_id: UUID) -> None:
        super().__init__(f"Supply {supply_id} not found")
        self.supply_id = supply_id


class SupplyCannotMarkAvailableError(Exception):
    """Attempted `mark_supply_available` from a disqualifying status.

    Single-source guard: `mark_supply_available` accepts ONLY
    `Unknown` (first-observation declaration). The `Recovering ->
    Available` transition has distinct audit semantics (recovery
    acknowledgement vs first observation) and exits exclusively via
    `restore_supply`. Strict-not-idempotent: re-marking an already-
    Available supply also raises. Per the Phoebus latched-alarm
    precedent: first-observation and recovery-confirmation are two
    different operator gestures even though they target the same
    `Available` status.
    """

    def __init__(self, supply_id: UUID, current_status: "SupplyStatus") -> None:
        super().__init__(
            f"Supply {supply_id} cannot be marked Available: currently in status "
            f"{current_status.value}, mark_supply_available requires "
            f"{SupplyStatus.UNKNOWN.value}"
        )
        self.supply_id = supply_id
        self.current_status = current_status


class SupplyCannotDegradeError(Exception):
    """Attempted `degrade_supply` from a disqualifying status (10a-b).

    Multi-source guard: source set is `{Unknown, Available, Recovering}`.
    Re-degrading an already-`Degraded` supply raises (strict-not-
    idempotent). `Unavailable` cannot transition directly to `Degraded`
    (must go via `mark_supply_recovering` first). Mirrors
    `SupplyCannotMarkAvailableError` shape.
    """

    def __init__(self, supply_id: UUID, current_status: "SupplyStatus") -> None:
        super().__init__(
            f"Supply {supply_id} cannot be degraded: currently in status "
            f"{current_status.value}, degrade_supply requires "
            f"{SupplyStatus.UNKNOWN.value}, {SupplyStatus.AVAILABLE.value}, "
            f"or {SupplyStatus.RECOVERING.value}"
        )
        self.supply_id = supply_id
        self.current_status = current_status


class SupplyCannotMarkUnavailableError(Exception):
    """Attempted `mark_supply_unavailable` from a disqualifying status (10a-b).

    Multi-source guard: source set is `{Unknown, Available, Degraded,
    Recovering}` — the widest source set of any Supply transition.
    Re-marking an already-`Unavailable` supply raises (strict-not-
    idempotent).
    """

    def __init__(self, supply_id: UUID, current_status: "SupplyStatus") -> None:
        super().__init__(
            f"Supply {supply_id} cannot be marked Unavailable: currently in status "
            f"{current_status.value}, mark_supply_unavailable requires "
            f"{SupplyStatus.UNKNOWN.value}, {SupplyStatus.AVAILABLE.value}, "
            f"{SupplyStatus.DEGRADED.value}, or {SupplyStatus.RECOVERING.value}"
        )
        self.supply_id = supply_id
        self.current_status = current_status


class SupplyCannotMarkRecoveringError(Exception):
    """Attempted `mark_supply_recovering` from a disqualifying status (10a-b).

    Single-source guard: source set is `{Unavailable}` only. Recovering
    is a transient observation that the underlying resource may be
    coming back; it has no meaning unless we were just in Unavailable.
    Strict-not-idempotent.
    """

    def __init__(self, supply_id: UUID, current_status: "SupplyStatus") -> None:
        super().__init__(
            f"Supply {supply_id} cannot be marked Recovering: currently in status "
            f"{current_status.value}, mark_supply_recovering requires "
            f"{SupplyStatus.UNAVAILABLE.value}"
        )
        self.supply_id = supply_id
        self.current_status = current_status


class SupplyCannotDeregisterError(Exception):
    """Attempted `deregister_supply` from a disqualifying status.

    Single disqualifying source: `Decommissioned` itself (the lifecycle
    terminal). Strict-not-idempotent: re-issuing on a Decommissioned
    Supply raises rather than silently succeeding, so operators get a
    clear 409 with the current status in the diagnostic. Mirrors the
    in-BC `SupplyCannot<Verb>Error` family shape (single + multi-source
    rejections all carry `current_status`) and aligns with the multi-
    state lifecycle-terminal precedent in `SubjectCannotDiscardError`
    and `AssetCannotDecommissionError`. (The Access BC's
    `ActorCannotDeactivateError` is single-arg by design: Actor's
    `active` is binary, so there is no informative status value to
    surface in the error message.)
    """

    def __init__(self, supply_id: UUID, current_status: "SupplyStatus") -> None:
        super().__init__(
            f"Supply {supply_id} cannot be deregistered: currently in status "
            f"{current_status.value}, deregister_supply requires any status "
            f"other than {SupplyStatus.DECOMMISSIONED.value}"
        )
        self.supply_id = supply_id
        self.current_status = current_status


class SupplyCannotRestoreError(Exception):
    """Attempted `restore_supply` from a disqualifying status (10a-b).

    Single-source guard: source set is `{Recovering}` only. Restore is
    the operator-acknowledgement that the supply is fully back; it
    only makes sense from `Recovering`. The `Unknown -> Available`
    transition has distinct audit semantics (first-observation
    declaration) and exits exclusively via `mark_supply_available`.
    Strict-not-idempotent. Per the Phoebus latched-alarm precedent
    and PackML CLEARING -> STOPPED -> RESETTING -> IDLE convention:
    explicit operator gesture required for full recovery
    (auto-timer-confirmed restore is deferred-with-trigger per Watch
    item 1 in [[project_supply_design]]).
    """

    def __init__(self, supply_id: UUID, current_status: "SupplyStatus") -> None:
        super().__init__(
            f"Supply {supply_id} cannot be restored: currently in status "
            f"{current_status.value}, restore_supply requires "
            f"{SupplyStatus.RECOVERING.value}"
        )
        self.supply_id = supply_id
        self.current_status = current_status


@bounded_name(max_length=SUPPLY_NAME_MAX_LENGTH, error_class=InvalidSupplyNameError)
@dataclass(frozen=True)
class SupplyName:
    """Display name for a supply. Trimmed; 1-200 chars.

    Eleventh occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `validate_bounded_text` helper (see
    `cora.shared.bounded_text`).
    """

    value: str


@dataclass(frozen=True)
class SupplyReason:
    """Free-form transition reason. Trimmed; 1-500 chars.

    Required on every transition event payload (10a-b adds four
    transition slices, each carrying a reason). Same shape as
    `RunAbortReason`, `PromotionReason`, Asset.condition reason
    fields. Free-form by design; structured taxonomies are deferred-
    with-trigger watch items.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=SUPPLY_REASON_MAX_LENGTH,
            error_class=InvalidSupplyReasonError,
        )
        object.__setattr__(self, "value", trimmed)


# MonitorRef bounds. Source kind = adapter discriminator (EpicsPv,
# P4pPv, TomoScanFile, LogTail, etc.); source_id = adapter-defined
# string identifying the specific source (PV name, file path).
SUPPLY_MONITOR_SOURCE_KIND_MAX_LENGTH = 50
SUPPLY_MONITOR_SOURCE_ID_MAX_LENGTH = 200


class InvalidMonitorRefError(Exception):
    """`MonitorRef` fields empty / whitespace-only / too long.

    Per [[project_supply_monitor_trigger_design]]: `source_kind` 1-50
    chars after trim (bare-str adapter discriminator, no closed enum
    per the same rationale as `Supply.kind`); `source_id` 1-200 chars
    after trim. HTTP 400.
    """


@dataclass(frozen=True)
class MonitorRef:
    """Identifies the external source of a Monitor-driven Supply transition.

    Carried on every transition event emitted by the
    `observe_supply_status` slice; absent (None) on operator-driven
    transitions. `source_kind` is a bare-str adapter discriminator
    (EpicsPv, P4pPv, TomoScanFile, LogTail, etc.) for the same
    reasons `Supply.kind` is bare per [[project_supply_design]]:
    future adapter sources are infinite. `source_id` is the
    adapter-defined identifier (PV name, file path, log channel) of
    the specific subscribed source.

    Construction trims + validates both fields via
    `validate_bounded_text`; the resulting object is hashable
    (frozen dataclass) and serializes as
    `{"source_kind": ..., "source_id": ...}` on the event payload
    per the cross-BC "typed in code, primitive in payload" convention.
    """

    source_kind: str
    source_id: str

    def __post_init__(self) -> None:
        trimmed_kind = validate_bounded_text(
            self.source_kind,
            max_length=SUPPLY_MONITOR_SOURCE_KIND_MAX_LENGTH,
            error_class=InvalidMonitorRefError,
        )
        trimmed_id = validate_bounded_text(
            self.source_id,
            max_length=SUPPLY_MONITOR_SOURCE_ID_MAX_LENGTH,
            error_class=InvalidMonitorRefError,
        )
        object.__setattr__(self, "source_kind", trimmed_kind)
        object.__setattr__(self, "source_id", trimmed_id)


class MonitorTriggerNotPermittedError(Exception):
    """`observe_supply_status` requested a transition Monitor cannot drive.

    Two transitions are operator-only per [[project_supply_design]]
    Anti-hooks: `Recovering -> Available` (must be `restore_supply`,
    latched-alarm precedent) and `Unknown -> Available` (must be
    `mark_supply_available`, first-observation operator declaration).
    No EPICS subscriber or other adapter can flip either via Monitor;
    this error fences both at the decider regardless of adapter
    cleverness. HTTP 400 (semantically a request the caller cannot
    issue, not a state-transition conflict).
    """

    def __init__(
        self,
        supply_id: UUID,
        requested_status: "SupplyStatus",
        current_status: "SupplyStatus",
    ) -> None:
        super().__init__(
            f"Supply {supply_id}: Monitor trigger cannot drive "
            f"{current_status.value} -> {requested_status.value}; "
            f"this transition is operator-only per the latched-alarm "
            f"semantics in project_supply_design."
        )
        self.supply_id = supply_id
        self.requested_status = requested_status
        self.current_status = current_status


@dataclass(frozen=True)
class Supply:
    """Aggregate root: a continuously-available resource.

    Slim aggregate per [[project_fold_cost_principles]]: identity +
    typed address + status + registered_at. Per-transition audit
    metadata (timestamps, reasons, triggers) lives in the event
    stream itself; the projection denormalizes the latest values for
    query-time access.

    `id` is the stable opaque handle. `(scope, kind, name)` is the
    operator-readable address; the projection enforces cross-stream
    uniqueness via UNIQUE INDEX (the aggregate cannot enforce cross-
    stream invariants without DCB).

    `status` defaults to `SupplyStatus.UNKNOWN`: the registration-
    time initial state per universal precedent. The genesis event
    `SupplyRegistered` carries no status field; the evolver sets
    `UNKNOWN` from the event type (same convention as
    `SubjectRegistered -> Received`).

    Future additive facets (per Watch items in
    [[project_supply_design]]): `bound_asset_id` (physical-equipment
    binding, mirrors 4f Subject pattern), `health` (orthogonal
    facet, mirrors 5g-b Asset.condition), `auto_clear_after` (per-
    kind timer for auto-restore), `capacity` (when first consumer
    needs quantity tracking). All land with safe defaults so pre-
    extension streams fold cleanly via the additive-state pattern.
    """

    id: UUID
    scope: SupplyScope
    # Carries a `DeferredVocabulary[SupplyKind]` marker per
    # [[project_structural_scope_design]] §"Marker convention": the
    # bare-str discriminator graduates to a typed `SupplyKind(StrEnum)`
    # when Watch item 4 fires (90+ days pilot data + <12 distinct
    # kinds + no new kind in trailing 60 days). LOCKSTEP with
    # `Method.needed_supplies` per the same marker convention; one
    # cannot graduate without the other. See
    # `cora.shared.scope_markers` for the marker shape.
    kind: Annotated[
        str,
        DeferredVocabulary(
            target_name="SupplyKind",
            trigger_doc="Supply.kind Watch item 4 trigger per project-structural-scope-design",
        ),
    ]
    name: SupplyName
    status: SupplyStatus = SupplyStatus.UNKNOWN
