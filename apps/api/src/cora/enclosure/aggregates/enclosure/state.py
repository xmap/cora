"""Enclosure aggregate state, enums, value objects, and domain errors.

An `Enclosure` is a beamline hutch, an experimental cabinet, or any
operator-visible containment volume whose access is gated by an
interlock chain (PSS / EPS / radiation interlock). Per
[[project_enclosure_stage1_design]] the aggregate observes the
external interlock as a one-axis `permit_status` (PERMITTED /
NOT_PERMITTED / UNKNOWN) without modeling the interlock chain or
severity scalars; the spine never authorizes shutter open / motion
start from this status (D6.L2 observation-axis-only anti-lock).

Two-tier identity per [[project_enclosure_stage1_design]]:

  - `Enclosure.id: EnclosureId` is the BC-local opaque PK for spine
    references within one deployment.
  - `Enclosure.name: EnclosureName` is the operator-readable display
    label; uniqueness is enforced at the projection-tier UNIQUE INDEX
    (aggregates cannot enforce cross-stream invariants without DCB).

`containing_asset_id` is a bare `UUID` cross-BC opaque pointer to the
Asset that physically contains the Enclosure (the hutch's beamline,
the cabinet's instrument). Cross-aggregate existence checks land in
later sub-slices via a handler-layer port; the decider stays pure.

Two-axis FSM per locked design:

  - Operational axis `permit_status` (mutated by `observe_enclosure_status`):
    UNKNOWN (genesis default) <-> PERMITTED <-> NOT_PERMITTED. No source-
    state guard; Monitor adapters drive transitions in either direction.
  - Structural axis `lifecycle` (mutated by `decommission_enclosure`):
    ACTIVE (genesis default) -> DECOMMISSIONED (terminal). `permit_status`
    is preserved across decommission as audit trail.

Fold-symmetric attribution pairs per [[project_fold_symmetry_design]]:
`registered_at + registered_by` at genesis; `decommissioned_at +
decommissioned_by` at terminal transition. Both `_by` fields are typed
`ActorId` so the fold-symmetry fitness test detects them structurally.

The `EnclosureName` VO (and its `InvalidEnclosureNameError` +
`ENCLOSURE_NAME_MAX_LENGTH` constant) is colocated here alongside the
aggregate per Supply / Facility precedent: the BoundedName VO that
feeds an aggregate identity field lives next to the aggregate rather
than in `_value_types.py` (which is reserved for NewType id aliases +
payload-side VOs like `EnclosureReason`).

Explicit NON-fields per the locked design L-state-7: NO `settings`, NO `schema`,
NO `persistent_id`, NO `alternate_identifiers`, NO `kind` enum, NO
`facility_code`, NO `upstream_enclosure_id`, NO `permit_observation_envelope`
(envelope is projection-only). Severity scalars (`severity`, `risk_level`,
`criticality`, `sil_level`, `hazard_level`, `signal_word`,
`vendor_status_code`) are banned by the D9-L1 fitness test.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.shared.bounded_text import bounded_name
from cora.shared.identity import ActorId

ENCLOSURE_NAME_MAX_LENGTH = 200


class InvalidEnclosureNameError(ValueError):
    """The supplied `Enclosure.name` is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Enclosure name must be 1-{ENCLOSURE_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


@bounded_name(max_length=ENCLOSURE_NAME_MAX_LENGTH, error_class=InvalidEnclosureNameError)
@dataclass(frozen=True)
class EnclosureName:
    """Operator-supplied display name for an Enclosure (1-200 chars, trimmed).

    Eleventh occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `@bounded_name` decorator (see
    `cora.shared.bounded_text`).
    """

    value: str


class EnclosurePermitStatus(StrEnum):
    """The Enclosure's observed access-permit state.

    Three values per [[project_enclosure_stage1_design]] D6.L2
    observation-axis-only anti-lock:

      - `Permitted`: external interlock chain reports the enclosure is
        access-permitted (operators may enter; the spine derives no
        beam / motion authorization from this).
      - `NotPermitted`: external interlock chain reports the enclosure
        is NOT access-permitted.
      - `Unknown`: registration-time default; no observation yet.

    The spine NEVER authorizes shutter open, motion start, or any
    actuation from this status. Authorization lives in the interlock
    PLC; this status records what the spine observed, nothing more.
    Severity scalars are banned by the D9-L1 fitness test; the status
    is a closed ternary, NOT a continuous risk level.

    Initial `Unknown` mirrors the universal industrial + cloud-native
    consensus on registration-time defaults (Tango UNKNOWN, EPICS UDF,
    Azure Resource Health Unknown, k8s Pending, Prometheus
    `up{}` UNKNOWN-before-first-scrape). The optimistic-Permitted
    default is an anti-pattern.
    """

    PERMITTED = "Permitted"
    NOT_PERMITTED = "NotPermitted"
    UNKNOWN = "Unknown"


class EnclosureLifecycle(StrEnum):
    """Structural lifecycle of an Enclosure.

    Two-state FSM per [[project_enclosure_stage1_design]] D10-L1
    no-Bypassed-state anti-lock:

      - `Active`: genesis state set by `register_enclosure`.
      - `Decommissioned`: terminal. The enclosure has been removed from
        service; no further transitions are valid.

    No `Bypassed` / `Maintenance` / `Suspended` state today: an
    operationally-bypassed interlock is the interlock vendor's concern,
    not the spine's. Expansion is deferred to rule-of-three.
    """

    ACTIVE = "Active"
    DECOMMISSIONED = "Decommissioned"


class EnclosureAlreadyExistsError(Exception):
    """Attempted to register an Enclosure whose stream already has events.

    Surfaces from `ConcurrencyError` translation in the
    `register_enclosure` handler when two operators race the same
    enclosure_id.

    Per [[project_genesis_error_classes]] this class stays un-hoisted;
    per-BC isinstance routing in the enclosure BC's exception handler
    outweighs the small saving from a generic alias.
    """

    def __init__(self, enclosure_id: EnclosureId) -> None:
        super().__init__(f"Enclosure {enclosure_id} already exists")
        self.enclosure_id = enclosure_id


class EnclosureNotFoundError(Exception):
    """Attempted an operation on an Enclosure whose stream has no events."""

    def __init__(self, enclosure_id: EnclosureId) -> None:
        super().__init__(f"Enclosure {enclosure_id} not found")
        self.enclosure_id = enclosure_id


class EnclosureCannotDecommissionError(Exception):
    """Decommission was attempted on an already-decommissioned Enclosure.

    Strict-not-idempotent per the `decommission_facility` precedent: a
    loud error surfaces operator intent mismatches (two operators racing
    to decommission the same enclosure) rather than silently absorbing
    the second call.
    """

    def __init__(self, enclosure_id: EnclosureId) -> None:
        super().__init__(f"Enclosure {enclosure_id} is already decommissioned")
        self.enclosure_id = enclosure_id


class EnclosureCannotObserveWhileDecommissionedError(Exception):
    """Permit observation was attempted on a decommissioned Enclosure.

    A Decommissioned Enclosure is a tombstone; no further permit
    transitions are accepted. Strict-not-idempotent. HTTP 409 at the
    route.
    """

    def __init__(
        self,
        enclosure_id: EnclosureId,
        current_lifecycle: "EnclosureLifecycle",
    ) -> None:
        super().__init__(
            f"Enclosure {enclosure_id} cannot observe permit status: currently in lifecycle "
            f"{current_lifecycle.value}, observe_enclosure_status requires "
            f"{EnclosureLifecycle.ACTIVE.value}"
        )
        self.enclosure_id = enclosure_id
        self.current_lifecycle = current_lifecycle


@dataclass(frozen=True)
class Enclosure:
    """Aggregate root: an interlock-gated containment volume.

    Slim aggregate per [[project_fold_cost_principles]]: identity +
    containing-Asset pointer + two-axis status (operational permit +
    structural lifecycle) + fold-symmetric attribution pairs.
    Per-transition audit metadata (reasons, triggers, monitor_ref)
    lives in the event stream itself; the projection denormalizes the
    latest values for query-time access.

    `id` is the stable opaque handle. `name` is the operator-readable
    label; the projection enforces cross-stream uniqueness via UNIQUE
    INDEX (the aggregate cannot enforce cross-stream invariants without
    DCB). `containing_asset_id` is a bare cross-BC opaque pointer; the
    decider stays pure and cross-aggregate existence checks land at the
    handler layer via a port (later sub-slices).

    No dataclass-level defaults: the genesis evolver constructs the
    aggregate with `permit_status=EnclosurePermitStatus.UNKNOWN` and
    `lifecycle=EnclosureLifecycle.ACTIVE` explicitly, mirroring the
    Facility / Supply evolver explicit-per-field-forwarding convention.
    `registered_at` / `registered_by` are non-nullable: every Enclosure
    on the spine has a genesis pair. `decommissioned_at` /
    `decommissioned_by` are `| None` because the terminal pair is
    genuinely absent until `EnclosureDecommissioned` lands.

    Per [[project_fold_symmetry_design]] the genesis envelope
    `occurred_at` is folded onto state as `registered_at` alongside the
    identity denorm `registered_by`. The terminal transition mirrors
    the pair: `decommissioned_at` and `decommissioned_by` are populated
    together by the `EnclosureDecommissioned` evolver fold. Both `_by`
    fields are typed `ActorId` so the fold-symmetry fitness test
    detects attribution fields structurally.
    """

    id: EnclosureId
    name: EnclosureName
    containing_asset_id: UUID
    permit_status: EnclosurePermitStatus
    lifecycle: EnclosureLifecycle
    registered_at: datetime
    registered_by: ActorId
    decommissioned_at: datetime | None
    decommissioned_by: ActorId | None


class MonitorTriggerNotPermittedError(Exception):
    """`observe_enclosure_status` carried a non-Monitor trigger.

    Per [[project_enclosure_stage1_design]] D6.L2 observation-axis-
    only anti-lock, the operational `permit_status` axis is reachable
    only via Monitor-driven inbound observation from the substrate;
    there is no operator path to Permitted / NotPermitted / Unknown.
    The command surface types `monitor_source_id` as `MonitorSourceId`
    so an operator cannot supply non-Monitor attribution at the type
    level; this error fences the same invariant defensively at the
    decider so a programmer mistake in a custom handler, test
    fixture, or future adapter cannot smuggle an operator-asserted
    permit status onto the spine.

    HTTP 400 (semantically a request the caller cannot issue, not a
    state-transition conflict).
    """

    def __init__(
        self,
        enclosure_id: EnclosureId,
        trigger: str,
    ) -> None:
        super().__init__(
            f"Enclosure {enclosure_id}: trigger {trigger!r} is not permitted on "
            f"observe_enclosure_status; only 'Monitor' is accepted per the "
            f"observation-axis-only anti-lock in project_enclosure_stage1_design."
        )
        self.enclosure_id = enclosure_id
        self.trigger = trigger
