"""Subject aggregate state, value objects, status enum, and domain errors.

`Subject` is the entity being measured, observed, or studied. Generic
across science domains: materials samples, biological specimens,
manufactured parts (including in-flight AM prints being formed during
the experiment), astronomical targets, computational subjects.

Subject identity crosses Run boundaries — the same Subject can be
referenced by multiple Runs (in-situ/operando experiments, repeat
measurements, etc.). Sample-environment rigs and sample changers are
`Equipment.Asset`s; the thing being formed/imaged/observed is the
`Subject`.


Minimal Subject: `id` + `name` + `status` (defaults `Received`).
Status lifecycle (the full transitions) shipped 4b-4d:
  - 4b: Received -> Mounted
  - 4c: Mounted -> Measured; Mounted | Measured -> Removed
  - 4d: Removed -> Returned | Stored | Discarded   (terminal disposition)
`hazard`, `custody`, `owner`, and the in-situ-during-Run observation
channel are deferred.

## Status as enum-in-state, derived-from-event-type-in-evolver

`SubjectStatus` is a `StrEnum` so the values would serialize naturally
as JSON-friendly strings IF carried in an event payload. Today they
aren't: state holds the enum (typed) and the evolver derives the new
status from the event TYPE (for example, folding `SubjectMounted` always
produces `status=MOUNTED`), exactly mirroring the
`ActorDeactivated -> active=False` precedent. The status field
never appears in an event payload — the event type IS the
state-change indicator.

The StrEnum-in-state, str-in-payload bridge will only fire if a future
event type genuinely needs to carry an arbitrary status as data (for example,
an admin "set-status" command for backfill). When that lands, the
evolver folds via `SubjectStatus(payload["status"])` and the bridge
becomes load-bearing. Until then the bridge is theoretical.

`SubjectRegistered` implies `Received` (genesis state set by the
evolver). Same additive-state pattern as `Actor.active`: the
field exists in state with a default, and future events that change
it land additively.

## In-situ subjects

For in-flight subjects (AM prints, in-situ-formed materials),
`Mounted` covers the active-formation period — same status, different
physical interpretation. If this overloading gets confused later,
split into a separate `Forming` state additively (state-level field
with a default; no event upcaster needed).

## Fifth bounded-name VO

`SubjectName` is the **fifth** trimmed-bounded-name VO after
`ActorName`, `ZoneName`, `ConduitName`, `PolicyName`. The shared
trim+length-check logic was hoisted to
`cora.shared.bounded_text.validate_bounded_text` once the
10th VO (PlanName) landed; SubjectName now calls that helper while
keeping its own frozen dataclass type and per-aggregate error class.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.shared.bounded_text import bounded_name, validate_bounded_text

SUBJECT_NAME_MAX_LENGTH = 200
SUBJECT_DISCARD_REASON_MAX_LENGTH = 500


class SubjectStatus(StrEnum):
    """The Subject's current lifecycle state.

    Transitions per-slice:
      - Received -> Mounted        (mount_subject, 4b)
      - Mounted -> Measured        (measure_subject, 4c)
      - Mounted | Measured -> Removed   (remove_subject, 4c)
      - Removed -> Returned        (return_subject, 4d)
      - Removed -> Stored          (store_subject, 4d)
      - Removed -> Discarded       (discard_subject, 4d)

    Returned / Stored / Discarded are terminal states (no further
    transitions). `Received` is the genesis state set by
    `register_subject`. The enum values are PascalCase strings
    (matching the BC-map status vocabulary) so log lines and DTOs
    read naturally without additional mapping.
    """

    RECEIVED = "Received"
    MOUNTED = "Mounted"
    MEASURED = "Measured"
    REMOVED = "Removed"
    RETURNED = "Returned"
    STORED = "Stored"
    DISCARDED = "Discarded"


class InvalidSubjectNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Subject name must be 1-{SUBJECT_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class SubjectAlreadyExistsError(Exception):
    """Attempted to register a subject whose stream already has events."""

    def __init__(self, subject_id: UUID) -> None:
        super().__init__(f"Subject {subject_id} already exists")
        self.subject_id = subject_id


class SubjectNotFoundError(Exception):
    """Attempted an operation on a subject whose stream has no events."""

    def __init__(self, subject_id: UUID) -> None:
        super().__init__(f"Subject {subject_id} not found")
        self.subject_id = subject_id


class SubjectCannotMountError(Exception):
    """Attempted to mount a subject not in the `Received` state.

    The current state is carried as `current_status` for diagnostics.
    Per-transition error class (matches `ActorCannotDeactivateError`
    naming) — each Subject transition gets its own
    `SubjectCannot<X>Error` rather than one generic
    `SubjectStateTransitionError`. With 7 states and ~6 transitions,
    per-transition is the right granularity for HTTP error mapping
    (each maps to 409) and for log-search clarity.
    """

    def __init__(self, subject_id: UUID, current_status: "SubjectStatus") -> None:
        super().__init__(
            f"Subject {subject_id} cannot be mounted: currently in state "
            f"{current_status.value}, mount requires {SubjectStatus.RECEIVED.value}"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class SubjectMountTargetUnavailableError(Exception):
    """Mount target Asset exists but is not in `Active` lifecycle.

    Mount requires the sample-environment Asset to be `Active`. If
    the operator names a `Commissioned`, `Maintenance`, or
    `Decommissioned` Asset, the mount is rejected. Cross-aggregate
    validation pattern: handler pre-loads the Asset, decider
    validates its lifecycle.

    Mapped to HTTP 409.
    """

    def __init__(self, subject_id: UUID, asset_id: UUID, current_lifecycle: str) -> None:
        super().__init__(
            f"Subject {subject_id} cannot be mounted on Asset {asset_id}: "
            f"Asset currently in lifecycle {current_lifecycle}, mount requires Active"
        )
        self.subject_id = subject_id
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class SubjectCannotMeasureError(Exception):
    """Attempted to measure a subject not in the `Mounted` state.

    Strict semantics: re-measuring an already-`Measured` subject also
    raises (rather than no-op or always-emit). Per-measurement detail
    (which scan, params, results) is out of scope at the aggregate
    level; that lives in `Run` observation channels later. The aggregate-level
    `Measured` status just means "has been measured at least once".

    See `SubjectCannotMountError` docstring for the per-transition-
    error rationale.
    """

    def __init__(self, subject_id: UUID, current_status: "SubjectStatus") -> None:
        super().__init__(
            f"Subject {subject_id} cannot be measured: currently in state "
            f"{current_status.value}, measure requires {SubjectStatus.MOUNTED.value}"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class SubjectCannotRemoveError(Exception):
    """Attempted to remove a subject from a state other than Mounted, Measured, or Received.

    Multi-source-state guard. `remove_subject` accepts:
      - `Mounted` (sample present but not yet measured -- operator
        changed mind, removing without measuring)
      - `Measured` (data collected, ready to remove)
      - `Received` (4f widening: sample arrived but was never
        mounted, OR sample mounted then dismounted -- in either case
        operator decided to remove without further use)

    The decider checks via tuple-membership; the error message lists
    all allowed source states for diagnostic clarity.

    See `SubjectCannotMountError` docstring for the per-transition-
    error rationale.
    """

    def __init__(self, subject_id: UUID, current_status: "SubjectStatus") -> None:
        super().__init__(
            f"Subject {subject_id} cannot be removed: currently in state "
            f"{current_status.value}, remove requires "
            f"{SubjectStatus.RECEIVED.value}, {SubjectStatus.MOUNTED.value}, "
            f"or {SubjectStatus.MEASURED.value}"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class SubjectCannotDismountError(Exception):
    """Attempted to dismount a subject not currently mounted (4f).

    Single-source guard at the status level: `dismount_subject`
    accepts only `Mounted` and `Measured` source states (a Received
    Subject has nothing to dismount; terminal-state Subjects are
    out-of-bounds entirely).

    Per-transition error class -- same naming convention as
    `SubjectCannotMountError`. Mapped to HTTP 409.
    """

    def __init__(self, subject_id: UUID, current_status: "SubjectStatus") -> None:
        super().__init__(
            f"Subject {subject_id} cannot be dismounted: currently in state "
            f"{current_status.value}, dismount requires "
            f"{SubjectStatus.MOUNTED.value} or {SubjectStatus.MEASURED.value}"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class SubjectCannotReturnError(Exception):
    """Attempted to return a subject not in the `Removed` state.

    Terminal disposition: `Returned` means the sample went back to
    its owner / submitter. Single-source guard (only `Removed` ->
    `Returned`); strict semantics means re-returning an already-
    `Returned` (or any non-`Removed`) subject raises.

    See `SubjectCannotMountError` docstring for the per-transition-
    error rationale.
    """

    def __init__(self, subject_id: UUID, current_status: "SubjectStatus") -> None:
        super().__init__(
            f"Subject {subject_id} cannot be returned: currently in state "
            f"{current_status.value}, return requires {SubjectStatus.REMOVED.value}"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class SubjectCannotStoreError(Exception):
    """Attempted to store a subject not in the `Removed` state.

    Terminal disposition: `Stored` means the sample was archived
    on-site (cold storage, sample library, etc.). Single-source
    guard; strict semantics.

    See `SubjectCannotMountError` docstring for the per-transition-
    error rationale.
    """

    def __init__(self, subject_id: UUID, current_status: "SubjectStatus") -> None:
        super().__init__(
            f"Subject {subject_id} cannot be stored: currently in state "
            f"{current_status.value}, store requires {SubjectStatus.REMOVED.value}"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class SubjectCannotDiscardError(Exception):
    """Attempted to discard a subject not in the `Removed` state.

    Terminal disposition: `Discarded` means the sample was destroyed
    (incinerated, washed away, otherwise irrecoverable). Single-source
    guard; strict semantics.

    See `SubjectCannotMountError` docstring for the per-transition-
    error rationale.
    """

    def __init__(self, subject_id: UUID, current_status: "SubjectStatus") -> None:
        super().__init__(
            f"Subject {subject_id} cannot be discarded: currently in state "
            f"{current_status.value}, discard requires {SubjectStatus.REMOVED.value}"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class InvalidSubjectDiscardReasonError(ValueError):
    """The supplied discard reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error. Mirrors the
    InvalidDatasetDiscardReasonError pattern (Data BC); free-form
    `str` (1-500 chars) with the same future-additive structured-
    taxonomy posture as Run BC reason fields.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Subject discard reason must be 1-{SUBJECT_DISCARD_REASON_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class SubjectDiscardReason:
    """Free-form discard reason for a Subject. Trimmed; 1-500 chars.

    Mirrors DatasetDiscardReason. The on-the-wire representation in
    `SubjectDiscarded.reason` is `str` (post-trim); the VO exists at
    decider-input time only.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=SUBJECT_DISCARD_REASON_MAX_LENGTH,
            error_class=InvalidSubjectDiscardReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@bounded_name(max_length=SUBJECT_NAME_MAX_LENGTH, error_class=InvalidSubjectNameError)
@dataclass(frozen=True)
class SubjectName:
    """Display name for a subject. Trimmed; 1-200 chars.

    Fifth occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `validate_bounded_text` helper (see
    `cora.shared.bounded_text`).
    """

    value: str


@dataclass(frozen=True)
class Subject:
    """Aggregate root: the entity being measured / observed / studied.

    `mounted_on_asset_id` is the sample-environment Asset the Subject
    is currently mounted on. Set on `mount_subject`, preserved through
    `measure_subject`, cleared on `remove_subject` and the terminal
    dispositions. None when the Subject is not mounted (Received,
    Removed, or any terminal state).
    """

    id: UUID
    name: SubjectName
    status: SubjectStatus = SubjectStatus.RECEIVED
    mounted_on_asset_id: UUID | None = None
