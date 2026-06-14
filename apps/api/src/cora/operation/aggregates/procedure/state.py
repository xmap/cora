"""Procedure aggregate state, value objects, status enum, and domain errors.

`Procedure` models one execution of an episodic operational task
(ISA-106 lens): bakeout, calibration sweep, optical alignment,
beam-mode change, recovery procedure, ID maintenance, KB switching.
Per the BC map: instrument-level AND facility-envelope procedures
share this aggregate. No batch identity (distinct from Run BC's
ISA-88 batch lens).

The aggregate is intentionally slim per
[[project_fold_cost_principles]]: identity + name + kind + target
Asset refs + status + optional parent_run_id. Per-step records
(Setpoint/Action/Check rows) live in a Logbook + Entry table parallel
to 6f-5b Observation (CORA's concrete realisation of the substream
concept; see [[project_logbook_entry_storage]] §Terminology); step
bodies do NOT fold into Procedure state.


Minimal Procedure: id + name + kind + target_asset_ids +
parent_run_id (optional) + status. Initial slices:
`register_procedure` (genesis -> Defined) and `get_procedure` (read).
Full FSM (Running / Completed / Aborted / Truncated transitions) +
per-step logbook follow. Projection + list_procedures follow.

## ProcedureStatus FSM (locked initial)

  Defined -> Running -> Completed | Aborted | Truncated

REVISED from BC map's `Idle -> Starting -> Running -> Verifying ->
Complete | Aborted` per the standards-corpus research at
[[project_operation_design]]: `Verifying` is NOT standards-blessed
at FSM level (PackML uses `Completing` for closeout/check work; OPC
UA Programs has no Verify state); per-step Check happens within
Running; transient states deferred until real async window appears
(Run BC precedent). Held/Resumed deferred to 10c-c per pilot need.

## Status as enum-in-state, derived-from-event-type-in-evolver

`ProcedureStatus` is a `StrEnum`; the values would serialize
naturally as JSON-friendly strings IF carried in an event payload.
State holds the enum (typed); the evolver derives the new status
from the event TYPE (`ProcedureRegistered -> DEFINED` etc.). Same
precedent as `SubjectStatus` / `FamilyStatus` / `AssetLifecycle`.

## Procedure.kind shape -- bare str (mirror Supply.kind lock)

`kind: str` is bare on Procedure state, NOT a VO. Validated at the
decider via `validate_bounded_text` (1-50 chars after trim) and at
the API boundary via Pydantic min_length / max_length. Mirrors
`Supply.kind` exactly:

  1. `kind` will eventually graduate to `ProcedureKind: StrEnum` once
     pilot vocabulary settles (Watch item 7 in
     [[project_operation_design]]). Migration `str -> StrEnum` is a
     clean parser change; `ProcedureKind(VO) -> ProcedureKind(StrEnum)`
     would break every type-annotated call site.
  2. `Supply.kind: str` and `AssetPort.signal_type: str` are the
     in-codebase precedents: bare-str discriminator with inline-
     validation, awaiting future enum promotion.

Documented starter vocabulary lives in [[project_operation_design]]
as guidance, not constraint: bakeout, calibration, alignment,
recovery, beam_mode_change, id_maintenance, kb_switching,
optical_alignment, vacuum_regeneration.

## Twelfth bounded-name VO

`ProcedureName` is the twelfth trimmed-bounded-name VO. Uses the
shared `validate_bounded_text` helper hoisted at the rule-of-three
trigger (`cora.shared.bounded_text`).

## Target_asset_ids -- eventual-consistency stance

The decider does NOT verify each Asset id refers to a real Asset
stream. Same precedent as Trust's Conduit zone refs (3b), Asset
parent refs (5b), and Method's needed_family_ids (6a). Empty
target_asset_ids is allowed (a procedure that doesn't act on a
specific Asset, for example facility-envelope beam-mode change). Existence
+ Decommissioned-lifecycle gating happens at start_procedure time
via `ProcedureStartContext` at start_procedure time (mirrors
`RunStartContext` from the Run BC).

## Parent_run_id -- standalone or Phase-of-Run

`parent_run_id: UUID | None` resolves the "Phase aggregate" question
flagged in [[project_run_parameters_design]] (which said "a Phase
aggregate in Operation BC will hold the start/stop event pair").
Resolution: a Phase IS a Procedure with `parent_run_id` set.
Standalone Procedures (bakeouts, calibration sweeps run between Runs)
have `parent_run_id = None`. The aggregate is one; the binding is
the discriminator.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal
from uuid import UUID

from cora.shared.bounded_text import bounded_name, validate_bounded_text
from cora.shared.logbook import LogbookFieldSpec, LogbookSchema
from cora.shared.scope_markers import Annotated, SubsumedBy
from cora.shared.text_bounds import REASON_MAX_LENGTH

if TYPE_CHECKING:
    from datetime import datetime

PROCEDURE_NAME_MAX_LENGTH = 200
PROCEDURE_KIND_MAX_LENGTH = 50

# per-Procedure step logbook constants.
LOGBOOK_KIND_ACTIVITY: Final = "activity"
"""Discriminator for the Procedure's per-step logbook.

Used as the `kind` value on `ProcedureActivitiesLogbookOpened` events. One
Procedure has at most one steps logbook (lazy open-on-first-write);
future distinct Procedure-side logbook kinds (operator-action audit,
hazard observations) would land as separate constants and separate
state fields, not as additional values for the same kind. Mirrors
LOGBOOK_KIND_OBSERVATION from Run BC."""

# Closed enum for the `step_kind` discriminator on per-step rows.
# The three values are CORA's rename of ISA-106's canonical
# Command/Perform/Verify triplet (renamed to avoid CQRS Command
# collision per [[project_operation_design]]). Future-additive
# operational vocabulary (for example "wait", "rollback") lands as
# code edits, not migrations (table column is plain TEXT, not a
# CHECK-constrained enum, mirroring Run BC's sampling_procedure
# precedent).
StepKind = Literal["setpoint", "action", "check"]
STEP_KIND_VALUES: frozenset[str] = frozenset({"setpoint", "action", "check"})

# Schema declaration for the steps logbook. Documentation-grade per
# [[project_logbook_entry_storage]]: declares the entry-row column
# shape so projections can read entry shape uniformly. The shared
# columns are the polymorphic-with-discriminator skeleton; the
# kind-specific body lives in the JSON `payload` column (per-kind
# Pydantic models guard the body shape at the API boundary).
STEPS_LOGBOOK_SCHEMA = LogbookSchema(
    fields={
        "step_kind": LogbookFieldSpec(
            type="string",
            description=(
                "Discriminator for the polymorphic step body. One of: "
                "'setpoint' (control-point change applied), 'action' "
                "(discrete operation performed), 'check' (verification "
                "recorded). CORA's rename of ISA-106's canonical "
                "Command/Perform/Verify triplet. The kind-specific "
                "JSON `payload` column is NOT declared here because "
                "LogbookFieldType is closed over primitives; per-kind "
                "body shape lives at the API layer (Pydantic per-kind "
                "models). See [[project_operation_design]]."
            ),
        ),
        "sampled_at": LogbookFieldSpec(
            type="datetime",
            description=(
                "phenomenonTime: when the step physically happened in "
                "the field (operator-recorded or instrument-clock)."
            ),
        ),
        "occurred_at": LogbookFieldSpec(
            type="datetime",
            description="When the handler appended the entry (CORA Clock port).",
        ),
        "recorded_at": LogbookFieldSpec(
            type="datetime",
            description="When Postgres wrote the row (DEFAULT now()).",
        ),
    },
    description=(
        "Per-Procedure step entries, polymorphic by step_kind "
        "(setpoint | action | check | future). One row per step; "
        "rows write directly to entries_operation_procedure_activities "
        "via the ActivityStore port (no per-row event on the Procedure "
        "stream). See [[project_operation_design]]."
    ),
)


class ProcedureStatus(StrEnum):
    """The Procedure's lifecycle state.

    Five values declared day one for forward-compat
    (additive-state pattern; legacy events fold cleanly because
    only DEFINED is reachable after register_procedure):

      - `Defined`     -- registration-time genesis; pre-execution.
                          Operator can edit / inspect / submit for
                          review (future Decision BC integration).
                          Cannot accept step events yet.
      - `Running`     -- post-start_procedure. Step events accepted
                          via append_activities.
      - `Completed`   -- happy path via complete_procedure.
                          Strict-not-idempotent.
      - `Aborted`     -- emergency exit via abort_procedure.
      - `Truncated`   -- retroactive cleanup via truncate_procedure.
                          Mirrors RunTruncated.

    `Verifying` and `Held / Resumed` are deliberately NOT in this
    enum. Per [[project_operation_design]] standards-corpus research:
    `Verifying` is NOT standards-blessed at FSM level (PackML uses
    `Completing` for closeout/check work; OPC UA Programs has no
    Verify state). Per-step Check happens within Running synchronously
    (via the Step logbook's check_passed field). Held / Resumed
    deferred until pilot operator feedback surfaces a need.

    Naming convention (per Run BC gate review): gerund /
    adjective for active steady-states (matches PackML / Bluesky);
    past-participle for terminals. `Defined` is past-participle (a
    procedure WAS defined); `Running` is gerund-as-adjective; the
    rest are past-participle terminals.

    Enum values are PascalCase strings (matches BC-map status
    vocabulary; log lines and DTOs read naturally without mapping).
    """

    DEFINED = "Defined"
    RUNNING = "Running"
    COMPLETED = "Completed"
    ABORTED = "Aborted"
    TRUNCATED = "Truncated"

    @property
    def is_terminal(self) -> bool:
        """True for the closed-set terminal states (Completed / Aborted /
        Truncated), False for Defined / Running.

        The FSM owns this truth so consumers (for example the Data BC's
        register_dataset, which requires a producing Procedure to be terminal
        before snapshotting its actuation kind) don't hard-code the terminal
        set and drift when a state is added."""
        return self in (
            ProcedureStatus.COMPLETED,
            ProcedureStatus.ABORTED,
            ProcedureStatus.TRUNCATED,
        )


class InvalidProcedureNameError(ValueError):
    """The supplied procedure name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Procedure name must be 1-{PROCEDURE_NAME_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class InvalidProcedureKindError(ValueError):
    """The supplied procedure kind is empty, whitespace-only, or too long.

    Free-form 1-50 chars today; future promotion to closed StrEnum
    is a watch item per [[project_operation_design]]. Raised by the
    `register_procedure` decider via `validate_bounded_text`, NOT by
    a `__post_init__` (kind is a bare `str` on Procedure state, not
    a VO; mirrors Supply.kind lock).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Procedure kind must be 1-{PROCEDURE_KIND_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class ProcedureAlreadyExistsError(Exception):
    """Attempted to register a procedure whose stream already has events."""

    def __init__(self, procedure_id: UUID) -> None:
        super().__init__(f"Procedure {procedure_id} already exists")
        self.procedure_id = procedure_id


class ProcedureNotFoundError(Exception):
    """Attempted an operation on a procedure whose stream has no events."""

    def __init__(self, procedure_id: UUID) -> None:
        super().__init__(f"Procedure {procedure_id} not found")
        self.procedure_id = procedure_id


class ProcedurePlanAssetDecommissionedError(Exception):
    """Procedure's target Assets include one or more Decommissioned at start.

    Re-validation of Asset state at start_procedure (NOT just register-
    time snapshot). If a target Asset got decommissioned between
    register_procedure and start_procedure, the Procedure can't proceed
    against the now-tombstoned Asset. Mirrors `RunPlanAssetDecommissionedError`.
    Mapped to HTTP 409.
    """

    def __init__(self, asset_ids: list[UUID]) -> None:
        super().__init__(
            f"Cannot start Procedure: the following target Assets are "
            f"Decommissioned: {[str(a) for a in asset_ids]}"
        )
        self.asset_ids = asset_ids


class ProcedureCapabilityExecutorMismatchError(Exception):
    """Procedure.capability_id points at a Capability whose executor_shapes
    do not include Procedure (cross-BC guard).

    Mapped to HTTP 409. Mirrors `MethodCapabilityExecutorMismatchError`.
    Surfaces when register_procedure binds to a
    Capability that only declares `ExecutorShape.METHOD`.
    """

    def __init__(self, procedure_id: UUID, capability_id: UUID) -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot bind to Capability {capability_id}: "
            f"Capability.executor_shapes does not include Procedure"
        )
        self.procedure_id = procedure_id
        self.capability_id = capability_id


class ProcedureBoundCapabilityDeprecatedError(Exception):
    """Attempted to conduct a recipe-driven Procedure whose pinned
    Capability is Deprecated.

    Capability deprecation is advisory at the Capability-aggregate layer
    (the Capability itself does not reject operations on Deprecated
    state), but conduct_procedure on a recipe-driven Procedure rejects:
    re-expanding a Recipe against a tombstoned Capability would silently
    execute against a contract operators have retired. Fires at the
    replay gate AFTER load_recipe_at_version succeeds and BEFORE the
    expansion port runs.

    Symmetric to start_run's RunBoundPlanDeprecatedError; the two
    together close the deprecation-at-execution-time gap surfaced by
    the 2026-06-04 domain harmony audit. Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, capability_id: UUID) -> None:
        super().__init__(
            f"Cannot conduct Procedure {procedure_id} against pinned "
            f"Capability {capability_id}: Capability is Deprecated"
        )
        self.procedure_id = procedure_id
        self.capability_id = capability_id


# Cap on the expanded step list at register_procedure_from_recipe time.
# Beyond this, the design memo's v2 lazy-walk reconsideration triggers
# (4D-tomography helical 150k-step case). v1 keeps a hard cap to bound
# the materialized expansion + the paginated append load.
RECIPE_EXPANSION_STEP_MAX = 10_000


class RecipeExpansionOverflowError(Exception):
    """The expanded flat step list exceeded `RECIPE_EXPANSION_STEP_MAX`.

    Carries the offending step count for operator diagnostics. v2 trigger:
    when a real consumer's single Recipe template legitimately exceeds
    the cap, the design memo's lazy-walk reconsideration fires. Mapped
    to HTTP 422 (parse-shape failure past the Pydantic boundary).
    """

    def __init__(self, step_count: int, cap: int) -> None:
        super().__init__(f"recipe expansion produced {step_count} steps; cap is {cap}")
        self.step_count = step_count
        self.cap = cap


class RecipeExpansionDeterminismError(Exception):
    """Expansion port returned different results for the same `(steps, bindings)`.

    The `(steps, bindings) -> tuple[Step, ...]` contract is pure
    (no clock, no port I/O, no randomness). The slice re-runs `expand`
    once at validation time and compares; a mismatch is a server-side
    bug in the expansion port or the recipe body, not operator error.
    Single-arg constructor (recipe_id) per the design memo lock;
    the diagnostic hashes go into the error message body.
    Mapped to HTTP 500.
    """

    def __init__(self, recipe_id: UUID) -> None:
        super().__init__(f"recipe expansion for Recipe {recipe_id} is non-deterministic")
        self.recipe_id = recipe_id


class ProcedureStepsForbiddenForRecipeDrivenError(Exception):
    """A non-empty `steps` list was supplied for a recipe-driven Procedure.

    Recipe-driven Procedures (created via `register_procedure_from_recipe`)
    have their step list pinned by `RecipeExpansionRecorded`; the
    `conduct_procedure` handler re-expands deterministically from the
    pinned Recipe + bindings and ignores any caller-supplied steps.
    Rather than silently override (which masks client bugs), the
    handler rejects up front per [[project-run-procedure-replay-design]]
    Anti-hook 7. Mapped to HTTP 400.
    """

    def __init__(self, procedure_id: UUID) -> None:
        super().__init__(
            f"Procedure {procedure_id} is recipe-driven; steps must be empty. "
            f"The conduct_procedure handler re-expands from RecipeExpansionRecorded."
        )
        self.procedure_id = procedure_id


class RecipeExpanderVersionMismatchError(Exception):
    """The currently-wired `RecipeExpander.version` differs from the pin.

    The `RecipeExpansionRecorded` event pins `expansion_port_version`;
    the replay path runs a strict-equals guard against the live port's
    `version` so a future v2 port cannot silently re-expand a v1-pinned
    Procedure with potentially different outputs. Today only v1 exists;
    this guard is the placeholder until a v2 expansion port lands with
    its routing layer. Mapped to HTTP 500.
    """

    def __init__(self, procedure_id: UUID, recorded_version: str, current_version: str) -> None:
        super().__init__(
            f"Procedure {procedure_id} recipe expansion was recorded with "
            f"port version {recorded_version!r}; the currently-wired port "
            f"reports {current_version!r}. Re-expansion would be unsafe."
        )
        self.procedure_id = procedure_id
        self.recorded_version = recorded_version
        self.current_version = current_version


class RecipeExpansionRecordNotFoundError(Exception):
    """The recipe-driven Procedure cannot locate the pinned expansion record.

    Raised by the `conduct_procedure` recipe-replay path
    (per [[project-run-procedure-replay-design]]) in any of three cases:

      - The Procedure stream carries no `RecipeExpansionRecorded`
        event (stream truncation or a direct event-store write left
        the genesis pair incomplete).
      - The `RecipeExpansionRecorded` payload is corrupt: one or more
        required keys are missing (caught by `pins_from_payload`'s
        defensive check).
      - The pinned Recipe stream itself is wholly empty when the
        handler calls `load_recipe_at_version` (the operator-pinned
        `recipe_id` references a Recipe with no genesis event).

    `register_procedure_from_recipe` emits both genesis events
    atomically so the first two cases are unreachable in normal
    operation; the third is unreachable while the event log stays
    append-only. The error covers operator escape hatches around
    stream truncation, manual event-store writes, or partial-write
    failures. Mapped to HTTP 500.
    """

    def __init__(self, procedure_id: UUID) -> None:
        super().__init__(
            f"Procedure {procedure_id} has recipe_id set but the pinned "
            f"RecipeExpansionRecorded event or the pinned Recipe stream "
            f"could not be located; replay cannot proceed."
        )
        self.procedure_id = procedure_id


class RecipeExpansionReplayMismatchError(Exception):
    """Replay-time hash drift on a recipe-driven Procedure.

    Raised when the recorded bindings no longer hash to
    `bindings_hash` (input drift, `mismatch_field='bindings'`) OR
    the freshly re-expanded steps no longer hash to `steps_hash`
    (expansion-logic drift, `mismatch_field='steps'`). Either case
    indicates the expansion port regressed or the recorded payload
    was mutated since write time, neither operator-correctable.
    Closed Literal discriminator instead of two error classes per
    [[project-run-procedure-replay-design]] Anti-hook 3. Mapped to
    HTTP 500.
    """

    def __init__(self, procedure_id: UUID, mismatch_field: Literal["bindings", "steps"]) -> None:
        super().__init__(
            f"Procedure {procedure_id} recipe expansion replay produced a "
            f"{mismatch_field}_hash mismatch against the recorded pin."
        )
        self.procedure_id = procedure_id
        self.mismatch_field = mismatch_field


class RecipeBindingsStaleAgainstCurrentCapabilityError(Exception):
    """The Recipe's BindingRefs no longer resolve against the current Capability schema.

    Cross-BC race: Capability was versioned independently after the
    Recipe's last write, and a binding name dropped (or the schema
    transitioned to None while the Recipe still carries BindingRefs).
    Operators resolve by versioning the Recipe (re-validating against
    the current Capability) or by versioning the Capability back if
    the schema change was unintended.

    Distinct from `RecipeBindingReferencesUnknownParameterError` (which
    fires at Recipe-write time against the schema-at-write-time): this
    error fires at register_procedure_from_recipe time against the
    CURRENT Capability state.

    Mapped to HTTP 422 (parse-shape failure past the Pydantic boundary).
    """

    def __init__(
        self,
        recipe_id: UUID,
        capability_id: UUID,
        missing_binding_names: frozenset[str],
    ) -> None:
        names = sorted(missing_binding_names)
        super().__init__(
            f"Recipe {recipe_id} BindingRefs are stale against the current "
            f"Capability {capability_id} schema; missing parameter(s): {names!r}. "
            f"Re-version the Recipe to align with the current Capability schema."
        )
        self.recipe_id = recipe_id
        self.capability_id = capability_id
        self.missing_binding_names = missing_binding_names


class InvalidRecipeBindingsError(ValueError):
    """`bindings` did not validate against `Capability.parameters_schema`.

    Raised by the JSON-Schema validator inside the
    `register_procedure_from_recipe` decider when operator-supplied
    `bindings` do not satisfy the bound Capability's declared schema.
    Distinct from `UnboundRecipeBindingError` (a BindingRef.name in the
    Recipe's steps has no entry in `bindings`); this error fires when
    `bindings` values fail the shape check.

    Mapped to HTTP 422 (parse-shape failure past the Pydantic boundary).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"invalid recipe bindings: {reason}")
        self.reason = reason


class ProcedureRequiresAvailableSupplyError(Exception):
    """No Supply registered for one of the parent Run's Method.needed_supplies kinds.

    Cross-BC gate: when a Procedure has `parent_run_id` set (Phase-of-Run),
    `start_procedure` inherits the parent Run's Method.needed_supplies
    requirement. This error fires when ZERO non-Decommissioned Supplies
    of a required kind are registered. Standalone Procedures (no
    parent_run_id) skip this gate today; Capability-level needed_supplies
    is a Watch item per [[project_supply_preflight_gate_design]].

    Mirrors `RunRequiresAvailableSupplyError`. Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, kind: str) -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot start: no Supply registered for "
            f"required kind {kind!r}. Register a Supply of that kind and mark "
            f"it Available before starting."
        )
        self.procedure_id = procedure_id
        self.kind = kind


class ProcedureSupplyCoverageMismatchError(Exception):
    """Supply registered for the required kind but none are Available.

    Cross-BC gate: at least one Supply of the required kind is
    registered (and not Decommissioned), but all have status in
    {Unknown, Degraded, Unavailable, Recovering}. Operator must mark
    one Available before starting.

    Mirrors `RunSupplyCoverageMismatchError`. Mapped to HTTP 409.
    """

    def __init__(
        self,
        procedure_id: UUID,
        kind: str,
        supply_status_summary: frozenset[tuple[UUID, str]],
    ) -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot start: required kind {kind!r} "
            f"has no Available Supply. Current statuses: "
            f"{sorted((str(sid), st) for sid, st in supply_status_summary)}. "
            f"Mark one Available before starting."
        )
        self.procedure_id = procedure_id
        self.kind = kind
        self.supply_status_summary = supply_status_summary


class ProcedureRequiresPermittedEnclosureError(Exception):
    """A referencing Enclosure is not currently Permitted-and-Active.

    Cross-BC gate: `start_procedure` derives the set of referencing
    Enclosures by walking `EnclosureLookup.find_for_assets` against
    the Procedure's `target_asset_ids`. Per L-pre-1 (always-derive-
    from-Asset-chain), the Procedure does NOT declare an explicit
    needed-enclosure list; the Asset chain IS the declaration. This
    error fires when EVERY referencing Enclosure is in
    `permit_status != "Permitted"` OR `lifecycle != "Active"` (the
    universally-not-permitted branch). When at least one row passes
    and at least one fails, the sibling
    `ProcedureEnclosureCoverageMismatchError` raises instead. An
    empty `target_asset_ids` (facility-envelope Procedure) yields
    zero referencing Enclosures and passes Permit-by-default;
    neither error fires.

    `enclosure_status_summary` carries `(enclosure_id, label)` tuples
    where `label` is the joined `permit_status|lifecycle` string for
    every failing Enclosure. Mirrors
    `RunRequiresPermittedEnclosureError` exactly. Mapped to HTTP 409
    per [[project_enclosure_stage1_design]].
    """

    def __init__(
        self,
        procedure_id: UUID,
        enclosure_status_summary: frozenset[tuple[UUID, str]],
    ) -> None:
        summary_sorted = sorted((str(eid), label) for eid, label in enclosure_status_summary)
        super().__init__(
            f"Procedure {procedure_id} cannot start: one or more referencing "
            f"Enclosures are not Permitted-and-Active. Current statuses: "
            f"{summary_sorted}. Walk each Enclosure to Permitted (and keep it "
            f"Active) before starting."
        )
        self.procedure_id = procedure_id
        self.enclosure_status_summary = enclosure_status_summary


class ProcedureEnclosureCoverageMismatchError(Exception):
    """Some referencing Enclosure rows resolved but coverage is incomplete.

    Cross-BC gate sibling to `ProcedureRequiresPermittedEnclosureError`,
    reserved for the symmetric-with-Supply two-error shape: this
    error fires when at least one referencing Enclosure is loaded
    AND at least one of those rows fails the Permitted-and-Active
    check while at least one OTHER row passes.

    Two error classes so operator-facing messaging can distinguish
    "no Enclosure rows pass" from "Enclosure rows exist, coverage
    incomplete". Mirrors `RunEnclosureCoverageMismatchError` exactly.
    Mapped to HTTP 409.
    """

    def __init__(
        self,
        procedure_id: UUID,
        enclosure_status_summary: frozenset[tuple[UUID, str]],
    ) -> None:
        summary_sorted = sorted((str(eid), label) for eid, label in enclosure_status_summary)
        super().__init__(
            f"Procedure {procedure_id} cannot start: referencing Enclosure(s) "
            f"failed the Permitted-and-Active gate. Current statuses: "
            f"{summary_sorted}. Walk each Enclosure to Permitted before starting."
        )
        self.procedure_id = procedure_id
        self.enclosure_status_summary = enclosure_status_summary


class ProcedureCannotStartError(Exception):
    """Attempted to start a Procedure not in `Defined`.

    Single-source guard: `start_procedure` accepts only `Defined`.
    Re-starting a `Running` Procedure raises (strict-not-idempotent);
    starting any terminal (Completed | Aborted | Truncated) raises.
    Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, current_status: "ProcedureStatus") -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot be started: currently in status "
            f"{current_status.value}, start requires {ProcedureStatus.DEFINED.value}"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class ProcedureCannotCompleteError(Exception):
    """Attempted to complete a Procedure not in `Running`.

    Single-source guard: `complete_procedure` accepts only `Running`.
    Re-completing a `Completed` Procedure raises (strict-not-idempotent);
    completing any other state (Defined | Aborted | Truncated) raises.
    Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, current_status: "ProcedureStatus") -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot be completed: currently in status "
            f"{current_status.value}, complete requires {ProcedureStatus.RUNNING.value}"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class ProcedureCannotAbortError(Exception):
    """Attempted to abort a Procedure not in `Running`.

    Single-source guard: `abort_procedure` accepts only `Running` (no
    Held state in the Procedure FSM today; deferred to 10c-c per pilot
    need). Aborting a `Defined` Procedure raises (use a different
    workflow, for example: never start it, then leave it Defined or
    extend the FSM with a cancel-defined slice if real); aborting any
    terminal raises (strict-not-idempotent). Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, current_status: "ProcedureStatus") -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot be aborted: currently in status "
            f"{current_status.value}, abort requires {ProcedureStatus.RUNNING.value}"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class ProcedureCannotTruncateError(Exception):
    """Attempted to truncate a Procedure not in `Running`.

    Single-source guard: `truncate_procedure` accepts only `Running`
    today (Held/Resumed deferred to future iteration). Mirrors
    `ProcedureCannotAbortError`'s source set: a Defined Procedure
    hasn't started so there's no execution to truncate; terminal
    Procedures are already closed (re-truncating a `Truncated`
    Procedure raises, strict-not-idempotent). Distinct from Abort
    at the lifecycle layer: Truncate is for Procedures that are
    already de-facto over (interrupted by infrastructure failure,
    operator returning Monday to mark a Friday-evening crash) and
    are being closed retroactively. The system does not detect
    de-facto-dead Procedures itself; operators must call truncate
    explicitly. Mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, current_status: "ProcedureStatus") -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot be truncated: currently in status "
            f"{current_status.value}, truncate requires {ProcedureStatus.RUNNING.value}"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class ProcedureCannotStartIterationError(Exception):
    """Attempted to start an iteration that fails a start-gate.

    Raised by the `start_iteration` decider for any of three reasons:
      - The Procedure is not in `Running` (iterations only exist within
        an active execution; same lifecycle gate as append_activities).
      - An iteration is already open (`current_iteration_index` is set);
        the open iteration must be ended first. Iterations do not nest.
      - The supplied `iteration_index` is not the strict successor of
        the current `iteration_count` (operator-supplied index must be
        monotonic with no gaps or duplicates, per the
        capture-don't-recompute principle).

    Carries `current_status`, the open `current_iteration_index` (None
    when none open), and `expected_iteration_index` / `iteration_index`
    so operator-facing messaging can name the gate that failed. Distinct
    class per verb per the conventions (Asset / Visit precedent). Mapped
    to HTTP 409.
    """

    def __init__(
        self,
        procedure_id: UUID,
        *,
        current_status: "ProcedureStatus",
        current_iteration_index: int | None,
        expected_iteration_index: int,
        iteration_index: int,
    ) -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot start iteration {iteration_index}: "
            f"status={current_status.value} (requires {ProcedureStatus.RUNNING.value}), "
            f"current_iteration_index={current_iteration_index} (requires no open "
            f"iteration), expected next index {expected_iteration_index}."
        )
        self.procedure_id = procedure_id
        self.current_status = current_status
        self.current_iteration_index = current_iteration_index
        self.expected_iteration_index = expected_iteration_index
        self.iteration_index = iteration_index


class ProcedureCannotEndIterationError(Exception):
    """Attempted to end an iteration that fails an end-gate.

    Raised by the `end_iteration` decider when:
      - The Procedure is not in `Running`.
      - No iteration is currently open (`current_iteration_index` is
        None); there is nothing to end.
      - The supplied `iteration_index` does not match the open
        `current_iteration_index`.

    Carries `current_status`, the open `current_iteration_index` (None
    when none open), and the supplied `iteration_index`. Distinct class
    per verb (sibling of `ProcedureCannotStartIterationError`). Mapped
    to HTTP 409.
    """

    def __init__(
        self,
        procedure_id: UUID,
        *,
        current_status: "ProcedureStatus",
        current_iteration_index: int | None,
        iteration_index: int,
    ) -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot end iteration {iteration_index}: "
            f"status={current_status.value} (requires {ProcedureStatus.RUNNING.value}), "
            f"current open iteration={current_iteration_index} (must equal "
            f"{iteration_index})."
        )
        self.procedure_id = procedure_id
        self.current_status = current_status
        self.current_iteration_index = current_iteration_index
        self.iteration_index = iteration_index


class ProcedureIterationLimitReachedError(Exception):
    """The convergence loop hit its consecutive-unconverged cap; refuse to start.

    A Procedure may declare `max_consecutive_unconverged_iterations` (the
    "patience" cap, from ML early-stopping vocabulary): the maximum number
    of consecutive iterations that may end NOT converged before the loop
    gives up. `start_iteration` rejects the next iteration once
    `consecutive_unconverged_iterations >= max_consecutive_unconverged_iterations`.
    The streak resets to 0 whenever an iteration ends `converged=True`, so
    a recovering loop keeps going; an iteration ending `converged=False`
    OR `converged=None` (no verdict) counts toward the cap.

    Distinct from the sequencing guard `ProcedureCannotStartIterationError`:
    this is an expected, operator-actionable budget outcome (stop and
    abort / complete the Procedure), not a malformed request. The cap is
    declaration-only and does NOT auto-abort the Procedure (mirrors
    `Agent.budget`: a cap is an attribute, not an FSM state). Mapped to
    HTTP 409.
    """

    def __init__(
        self,
        procedure_id: UUID,
        *,
        consecutive_unconverged_iterations: int,
        max_consecutive_unconverged_iterations: int,
    ) -> None:
        super().__init__(
            f"Procedure {procedure_id} cannot start another iteration: "
            f"{consecutive_unconverged_iterations} consecutive unconverged "
            f"iterations reached the cap of {max_consecutive_unconverged_iterations}. "
            f"Resolve by completing or aborting the Procedure (a converged "
            f"iteration would reset the streak)."
        )
        self.procedure_id = procedure_id
        self.consecutive_unconverged_iterations = consecutive_unconverged_iterations
        self.max_consecutive_unconverged_iterations = max_consecutive_unconverged_iterations


class InvalidProcedureIterationCapError(ValueError):
    """The supplied max_consecutive_unconverged_iterations cap is below 1.

    The patience cap is optional (None = no cap); when present it must be
    >= 1 (a cap of 0 would forbid even the first iteration). Validated at
    the API boundary via Pydantic `ge=1` AND defensively at the
    register deciders. Mapped to HTTP 400.
    """

    def __init__(self, value: int) -> None:
        super().__init__(
            f"max_consecutive_unconverged_iterations must be >= 1 when set (got: {value})"
        )
        self.value = value


class InvalidProcedureTruncateReasonError(ValueError):
    """The supplied truncate reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error. Sibling of
    `InvalidProcedureAbortReasonError`; same shape, distinct class for
    BC-local HTTP-status registration. Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Procedure truncate reason must be 1-{REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidProcedureIterationEndReasonError(ValueError):
    """The supplied iteration-end reason is whitespace-only or too long.

    The end-iteration reason is OPTIONAL (None is allowed); when present
    it is trimmed and bounded 1-500 chars. Validated at the API boundary
    via Pydantic min_length / max_length AND defensively at the
    `end_iteration` decider via `validate_bounded_text` so direct
    in-process callers (sagas, tests) get the same trim + whitespace-only
    rejection as abort / truncate. Sibling of
    `InvalidProcedureAbortReasonError`; distinct class for BC-local
    HTTP-status registration. Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Procedure iteration-end reason must be 1-{REASON_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidProcedureInterruptedAtError(ValueError):
    """The supplied truncate `interrupted_at` is in the future relative to `now`.

    `interrupted_at` is the operator's best guess at when the actual
    interruption happened, separate from `occurred_at` (when the
    truncate command was processed). The two timestamps can be hours
    or days apart for weekend / overnight interruptions, but
    `interrupted_at` MUST not be later than `now`: you cannot have
    been interrupted in the future. Validated defensively at the
    decider; mirrors `InvalidRunInterruptedAtError`. Mapped to HTTP 400.
    """

    def __init__(self, interrupted_at: "datetime", now: "datetime") -> None:
        super().__init__(
            f"interrupted_at {interrupted_at.isoformat()} is in the future "
            f"relative to now {now.isoformat()}"
        )
        self.interrupted_at = interrupted_at
        self.now = now


class InvalidStepKindError(ValueError):
    """The supplied step_kind is not in the allowed set.

    Pydantic catches this at the API boundary via `Literal[...]` on
    the request body. The handler ALSO validates against
    `STEP_KIND_VALUES` so direct in-process callers (sagas, tests)
    get the same protection. Mirrors `InvalidSamplingProcedureError`
    from Run BC. Mapped to HTTP 400.
    """

    def __init__(self, value: str, allowed: frozenset[str]) -> None:
        super().__init__(f"Procedure step_kind must be one of {sorted(allowed)} (got: {value!r})")
        self.value = value
        self.allowed = allowed


class ProcedureStepsLogbookClosedError(Exception):
    """Cannot append step to a Procedure in a terminal status.

    Per [[project_operation_design]] the Procedure FSM's terminals
    (Completed | Aborted | Truncated) implicitly close the steps
    logbook; no explicit `ProcedureStepsLogbookClosed` event is
    emitted. The `append_activities` handler raises this when
    a writer attempts to append after the Procedure has terminated.
    Mirrors `RunObservationLogbookClosedError` from Run BC. Mapped to
    HTTP 409.

    Note: appending to a `Defined` (pre-start) Procedure also raises
    this; steps are only valid in `Running`.
    """

    def __init__(self, procedure_id: UUID, current_status: "ProcedureStatus") -> None:
        super().__init__(
            f"Procedure {procedure_id} steps logbook is closed: currently in "
            f"status {current_status.value}; appends require {ProcedureStatus.RUNNING.value}"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class InvalidProcedureAbortReasonError(ValueError):
    """The supplied abort reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error so direct in-process
    callers (sagas, tests) get the same protection. Same precedent as
    `InvalidRunAbortReasonError`.

    Free-form `str` (1-500 chars). Structured taxonomy is future-additive
    if vocabulary convergence across real aborts surfaces, or if Decision
    BC adopts ProcedureAbort with structured-context queries. Mirrors
    Run BC's posture exactly. Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Procedure abort reason must be 1-{REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


@bounded_name(
    max_length=PROCEDURE_NAME_MAX_LENGTH,
    error_class=InvalidProcedureNameError,
)
@dataclass(frozen=True)
class ProcedureName:
    """Display name for a procedure. Trimmed; 1-200 chars."""

    value: str


@dataclass(frozen=True)
class ProcedureTruncateReason:
    """Free-form truncate reason. Trimmed; 1-500 chars.

    Sibling of `ProcedureAbortReason`; same shape (trimmed +
    bounded), distinct class for BC-local HTTP-status registration.
    Mirrors Run BC's `RunTruncateReason`. The on-the-wire
    representation in `ProcedureTruncated.reason` is `str` (post-
    trim); the VO exists at decider-input time only.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidProcedureTruncateReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class ProcedureAbortReason:
    """Free-form abort reason. Trimmed; 1-500 chars.

    Domain VO (not just `str`) so the decider validates uniformly via
    the shared `validate_bounded_text` helper. The on-the-wire
    representation in `ProcedureAborted.reason` is `str` (post-trim)
    for payload simplicity; the VO exists at decider-input time only.
    Sibling of `RunAbortReason`; same shape, distinct class for
    BC-local HTTP-status registration.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidProcedureAbortReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Procedure:
    """Aggregate root: one execution of an episodic operational task.

    Slim aggregate per [[project_fold_cost_principles]]: identity +
    name + kind + target Asset refs + status + optional Run binding.
    Per-step records (Setpoint/Action/Check) live in a Logbook + Entry
    table (see [[project_logbook_entry_storage]]); the step
    bodies do NOT fold into this state.

    `id` is the stable opaque handle. `name` is operator-readable.
    `kind` is the free-form ISA-106 procedure-kind discriminator
    (bakeout / calibration / alignment / etc.); bare str per the
    Supply.kind lock precedent.

    `target_asset_ids` is a frozenset of Asset ids the procedure
    acts on. Mirrors `Plan.asset_ids` shape; eventual-
    consistency stance for existence verification. Empty set is
    valid for facility-envelope procedures (beam-mode change) that
    don't act on a specific Asset instance.

    `parent_run_id` resolves the Phase aggregate question (per
    [[project_operation_design]]): None = standalone procedure
    (bakeout, calibration sweep run between Runs); UUID = Phase-of-
    Run (calibration sweep invoked mid-Run, formerly the planned
    "Phase" aggregate from [[project_run_parameters_design]] §6g-c).

    `status` defaults to `ProcedureStatus.DEFINED`: the
    registration-time initial state. The genesis event
    `ProcedureRegistered` carries no status field; the evolver sets
    `DEFINED` from the event type (same convention as
    `SubjectRegistered -> Received` and `SupplyRegistered ->
    Unknown`).

    Future additive facets (per Watch items in
    [[project_operation_design]]): `activity_logbook_id` (lazy-opened
    when first step lands), expected-step-count for
    progress projections, etc. All land with safe defaults via the
    additive-state pattern.

    `Procedure.kind` is intentionally a bare `str` (NOT a typed
    `ProcedureTemplate` ref). The template role is already filled by
    `Capability` (parameter contract) and `Recipe` (step expansion via
    `register_procedure_from_recipe`); promoting an independent
    `ProcedureTemplate` aggregate would duplicate that role for one
    ISA-106 procedure-of-procedures concept. The `SubsumedBy` marker
    annotation on the field records this stance permanently. See
    `cora.shared.scope_markers` for the marker shape and
    [[project_structural_scope_design]] for the rationale.
    """

    id: UUID
    name: ProcedureName
    # Carries a `SubsumedBy[ProcedureTemplate <- (Capability, Recipe)]`
    # marker per [[project_structural_scope_design]] §"Marker convention":
    # do NOT promote `ProcedureTemplate` as an independent aggregate; the
    # template role is already filled by Capability + Recipe. The marker
    # is PERMANENT (stronger than DeferredVocabulary). See
    # `cora.shared.scope_markers` for the marker shape.
    kind: Annotated[
        str,
        SubsumedBy(
            subsumed_target_name="ProcedureTemplate",
            subsuming_aggregate_names=("Capability", "Recipe"),
        ),
    ]
    target_asset_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    status: ProcedureStatus = ProcedureStatus.DEFINED
    parent_run_id: UUID | None = None
    activity_logbook_id: UUID | None = None
    """Lazy-opened on first `append_activities`.

    None until the first step is appended; populated by the
    `ProcedureActivitiesLogbookOpened` envelope event the handler emits
    on the Procedure stream. Mirrors `Run.observation_logbook_id`.
    Per the lazy-open pattern: no eager open at start_procedure,
    no Closed event (terminal Procedure.status implicitly closes
    via `ProcedureStepsLogbookClosedError`).
    """
    capability_id: UUID | None = field(default=None)
    """Optional binding to the universal Capability template (Recipe
    BC) this Procedure realizes as a Procedure-shaped executor.
    OPTIONAL so pre-binding Procedures keep working without bulk
    migration; a strict follow-up may REQUIRE the binding per
    Pattern P (or accept that ceremony Procedures stay un-bound when
    no Capability template applies). Same additive-state shape as
    Method.capability_id."""
    recipe_id: UUID | None = field(default=None)
    """Optional pointer to the Recipe (Recipe BC) whose steps were
    expanded into this Procedure via the
    `register_procedure_from_recipe` slice. None for legacy Procedures
    (registered via `register_procedure` with an inline step list) and
    for ceremony Procedures with no Recipe binding.

    The Recipe is the source of truth for the expansion (Recipe.capability_id
    points at the Capability that supplied the parameters_schema this
    expansion was bound against). `capability_id` above is preserved as
    a denorm for audit-by-Capability read paths without requiring a
    Recipe join. Both fields are set by `register_procedure_from_recipe`
    to the same logical binding."""
    current_iteration_index: int | None = field(default=None)
    """The convergence-loop iteration currently open, or None.

    Set to the operator-supplied `iteration_index` by
    `ProcedureIterationStarted` and cleared back to None by
    `ProcedureIterationEnded`. Acts as the open/close marker that lets
    the deciders forbid nested iterations (start while one is open) and
    forbid ending when none is open. Additive-state default None: legacy
    streams and non-iterative Procedures fold cleanly."""
    iteration_count: int = field(default=0)
    """How many convergence-loop iterations have begun on this Procedure.

    Denorm count (NOT a history; the boundary events are the history),
    incremented by `ProcedureIterationStarted`. Mirrors
    `Run.adjustment_count`. Surfaced as the `iteration_count` projection
    column so "how many iterations did this alignment take" is a plain
    SQL question. Additive-state default 0."""
    consecutive_unconverged_iterations: int = field(default=0)
    """How many iterations in a row have ended NOT converged.

    Folded by `ProcedureIterationEnded`: +1 when `converged` is not True
    (False OR None), reset to 0 when `converged` is True. This is the
    running "patience" streak the `start_iteration` decider checks against
    `max_consecutive_unconverged_iterations`. Additive-state default 0."""
    max_consecutive_unconverged_iterations: int | None = field(default=None)
    """Optional cap on `consecutive_unconverged_iterations`; None = no cap.

    The "patience" limit (ML early-stopping vocabulary): once the streak
    reaches this, `start_iteration` refuses the next iteration with
    `ProcedureIterationLimitReachedError` (the operator then aborts or
    completes; no auto-abort, mirroring `Agent.budget`). Operator-supplied
    at register time (>= 1 when set); declaration-only, never an FSM
    state. Additive-state default None: legacy + uncapped Procedures fold
    cleanly."""
    actuation_kind: str | None = field(default=None)
    """The raw `ActuationKind` value (Physical / Simulated / Hybrid) the
    Conductor observed during the conduct that drove this Procedure to a
    terminal state, or None.

    Set by the `ProcedureCompleted` / `ProcedureAborted` terminal arms
    from the event's `actuation_kind`; None while Defined / Running and
    for completes/aborts issued outside a conduct. This is the gate
    carrier: `register_dataset` reads it off a loaded producing Procedure
    and snapshots it onto the Dataset, where `promote_dataset` blocks
    Simulated / Hybrid origins. The Operation BC owns the `ActuationKind`
    enum; state stores the raw string (cross-BC string-snapshot seam,
    mirroring how the Data BC stores it). Additive-state default None:
    legacy + pre-activation streams fold cleanly."""
