"""Run aggregate state, value objects, status enum, and domain errors.

`Run` is the actual-execution layer in CORA's recipe ladder
(Method → Practice → Plan → **Run**). One Run = one execution
instance with batch identity, FSM, audit trail, and references to
the bound Plan + (optional) Subject.

Per the BC map, Run is a **Lifecycle Aggregate**: terminal states
(`Completed`, `Aborted`, `Stopped`, `Truncated`) end the stream
naturally. After 6f-2+ ships those, the design implication (per
`project_fold_cost_principles.md`) is that the completion event
should carry summary state so downstream consumers don't have to
re-fold per-step history just to ask "what happened in Run X?".

## Aggregate scope

Run state:
  - `id` + `name` (RunName: 11th bounded-name VO)
  - `plan_id: UUID` — eventual-consistency ref to the Plan being
    executed; loaded at handler-load time for re-validation
  - `subject_id: UUID | None` — the Subject being measured, or
    None for dark-field / flat-field calibration runs (per
    beamline-domain convention; calibration data is consumed
    alongside sample data within the same analysis pipeline)
  - `status: RunStatus` (the steady-state and terminal transitions
    are the full FSM)

The active steady-state is named `Running` (not `Started`) per
the gerund/adjective convention used by ISA-88 / PackML
(`Execute`) and Bluesky beamline software (`running`). Past-
participle names like `Started` linguistically suggest a point-
in-time event, not an ongoing state — those belong on event
classes (`RunStarted` is correctly named) but not on the status
enum.

Run does NOT directly reference Asset(s) — those are reachable via
`plan.asset_ids`. State stays slim per Q4-style reasoning: only
fields decider invariants need.

## Why subject_id is Optional (not Required)

Beamline operations frequently include calibration runs that have
no Subject:
  - Dark-field: detector measures background noise (no beam, no sample)
  - Flat-field: detector measures beam profile (beam, no sample)
  - Energy calibration: standard reference samples (different from
    user Subject)

These produce data consumed by the analysis pipeline for actual
sample Runs. They share the Run lifecycle, audit, and FSM with
sample runs — only the Subject binding differs. Modeling them as
the same aggregate with `subject_id: UUID | None` is cleaner than
a discriminator field or a separate `CalibrationRun` aggregate.

Confirmed by Bluesky / beamline-software domain research: dark-
field acquisition is "an integral part of beamline operations".
Subject-optional Run is the right modeling choice.

## Cross-aggregate validation at Run-start (gate-review Q2 / Q5)

The `start_run` handler pre-loads Plan + Subject (if subject_id) +
each bound Asset (from `plan.asset_ids`), bundles them into a
`RunStartContext`, and hands it to the pure decider. The decider
treats them as opaque domain data and validates:

  - state must be None (defensive: stream collision)
  - plan must not be Deprecated
  - subject (if present) must be in {Mounted, Measured}
  - no bound Asset may be Decommissioned
  - capability superset RE-VALIDATED: union(asset.family_ids) ⊇
    method.needed_family_ids (from current Asset state, not the
    Plan-bind snapshot — drift is real and Run is the last gate)
  - name validation (via RunName VO)

Same canonical pattern as `PlanBindingContext` (6e-1). Documented
in CONTRIBUTING.md as the cross-aggregate-validation idiom.

## Status as enum-in-state, derived-from-event-type-in-evolver

Same precedent as Method / Practice / Plan / Family /
Subject / Asset. RunStatus is a `StrEnum`; the evolver derives
the new status from the event TYPE per match arm. Status is NOT
carried in event payloads.

## Eleventh bounded-name VO

`RunName` calls the shared `validate_bounded_text` helper hoisted in
6e-1 (`cora.shared.bounded_text`). Same pattern as the prior 10.

## Known gaps documented (gate-review Q3)

  - **No Supply availability check**: Track B Supply BC not shipped;
    Run-start does NOT verify beam/power/gas availability. Lands
    when Supply BC ships.
  - **No Decision approval check**: Decision BC not shipped; Run-
    start does NOT require an Approved Decision. Lands when
    Decision BC ships.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Literal
from uuid import UUID

from cora.shared.bounded_text import bounded_name, validate_bounded_text
from cora.shared.identifier import (
    IDENTIFIER_SCHEME_MAX_LENGTH,
    IDENTIFIER_VALUE_MAX_LENGTH,
    Identifier,
    InvalidIdentifierError,
)
from cora.shared.identity import ActorId
from cora.shared.logbook import LogbookFieldSpec, LogbookSchema
from cora.shared.text_bounds import REASON_MAX_LENGTH

RUN_NAME_MAX_LENGTH = 200
# cardinality cap on the AsShot pin set
# (Run.pinned_calibration_ids). Mirrors Data BC's
# DATASET_USED_CALIBRATIONS_MAX_ENTRIES exactly (same default + same
# precedent justification: per-entry existence is NOT checked at the
# write path — revision-cited atomic IDs are cross-BC eventual-
# consistency citations per [[project_calibration_design]]
# anti-hook #3 — but unbounded set growth would still bloat events +
# payloads with no domain justification).
RUN_PINNED_CALIBRATIONS_MAX_ENTRIES = 64

# `Identifier(scheme, value)` carries open-scheme anti-corruption refs
# mirroring the Safety BC's ExternalBinding shape (proposal / btr /
# lab_visit / session / cycle / visit, etc.). Same bounded lengths so
# the round-trip with `ExternalBinding`-keyed clearance coverage
# queries stays symmetric. The VO + bounds live at
# `cora.shared.identifier`; the Run BC keeps the
# `RUN_EXTERNAL_REF_*` names as aliases for backward-compat (existing
# routes / tools / tests reference them).
RUN_EXTERNAL_REF_SCHEME_MAX_LENGTH = IDENTIFIER_SCHEME_MAX_LENGTH
RUN_EXTERNAL_REF_ID_MAX_LENGTH = IDENTIFIER_VALUE_MAX_LENGTH

# Observation polymorphic logbook constants.
READING_CHANNEL_NAME_MAX_LENGTH = 255
READING_UNITS_MAX_LENGTH = 64
LOGBOOK_KIND_OBSERVATION: Final = "observation"
"""Discriminator string for the Run's observation logbook.

Used as the `kind` value on `RunObservationLogbookOpened` events. One Run
has at most one observation logbook (lazy open-on-first-write); future
distinct logbook kinds (for example: hazard events, operator-action
audit) would land as separate constants and separate state fields,
not as additional values for the same kind."""

# Closed enum for the SOSA-aligned `sampling_procedure` discriminator
# field on Observation rows. Values are Bluesky-aligned operator vocabulary;
# additions land as code edits, not migrations (table column is plain
# TEXT, not a CHECK-constrained enum, per [[project_run_reading_design]]).
# 6f-5b shipped "baseline" (snapshot at run boundary). 6f-5c adds
# "monitor" (sub-Hz time-series during run). Future values ("primary",
# "triggered") land additively.
SamplingProcedure = Literal["baseline", "monitor"]
SAMPLING_PROCEDURE_VALUES: frozenset[str] = frozenset({"baseline", "monitor"})

# Schema declaration for the observation logbook. Documentation-grade per
# [[project_logbook_entry_storage]]: declares the entry-row column
# shape so projections can read entry shape uniformly without per-BC
# adapters. Lives here (not in a slice module) because the schema is
# attached to the Run aggregate, not to one specific writer.
OBSERVATION_LOGBOOK_SCHEMA = LogbookSchema(
    fields={
        "channel_name": LogbookFieldSpec(
            type="string",
            description="Sensor or motor identifier (operator-meaningful name).",
        ),
        "value": LogbookFieldSpec(
            type="float",
            description="Scalar observation value. NaN and Infinity rejected at write time.",
        ),
        "units": LogbookFieldSpec(
            type="string",
            description="Optional unit string (for example 'K', 'mm', 'mA').",
        ),
        "sampling_procedure": LogbookFieldSpec(
            type="string",
            description=(
                "SOSA-aligned discriminator (W3C SOSA 2023 sosa:samplingProcedure). "
                "Values: 'baseline' (snapshot at run boundary), 'monitor' (sub-Hz "
                "time-series during run), and future-additive operational vocabulary."
            ),
        ),
        "sampled_at": LogbookFieldSpec(
            type="datetime",
            description="SOSA phenomenonTime: when the sensor captured the value.",
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
        "Per-Run sensor and motor observation entries, polymorphic by sampling_procedure "
        "(baseline | monitor | future). One row per observation; rows write directly to "
        "entries_run_observations via the ObservationStore port (no per-row event on the "
        "Run stream). See [[project_run_reading_design]]."
    ),
)


class RunStatus(StrEnum):
    """The Run's lifecycle state.

    6f-4 closes the FSM with the partial-data terminal. The full
    set is now: Running plus the Held pause-state plus four
    reachable terminals (Completed, Aborted, Stopped, Truncated).

      Running (6f-1)
        ⇄ Held (6f-3 hold/resume; bidirectional cycle, unlimited)
        → Completed (6f-2 happy-path; single-source from Running)
        → Aborted (6f-2 emergency; multi-source from Running | Held)
        → Stopped (6f-3 controlled exit; multi-source from Running | Held)
        → Truncated (6f-4 partial-data terminal; multi-source from
                     Running | Held)

    Stopped vs Truncated (6f-4 lifecycle-layer distinction):
    Stopped is a controlled exit while the system is responsive and
    the operator decides to end the Run early; data up to the stop
    point is valid. Truncated is a cleanup terminal for a Run that
    became known-dead through interruption (power loss, process
    crash, hardware fault) and is being closed retroactively. The
    Run was already de-facto over before the operator could mark
    it; truncation captures that fact plus the operator's best
    guess at when the actual interruption occurred (optional
    interrupted_at on RunTruncated). The system does not detect
    de-facto-dead Runs itself today (gate-review L4-followup);
    operators must call truncate explicitly.

    Why complete_run is single-source while stop/abort_run are
    multi-source (gate-review 6f-3 Q1 lock): completion claims
    achievement, which requires active work happening at the
    moment of completion. Stop and abort are exits; they don't
    require active work, only any non-terminal state. Operators
    wanting to mark a held run as complete must Resume → Complete,
    which preserves clearer audit semantics than a bare Held →
    Complete transition.

    Plus transient states (Starting, Stopping, Aborting,
    Holding, Unholding, Completing) get evaluated when DAQ-channel
    integration arrives (6f-5+); only added if there's a real
    async period between command-arrival and event-emit at the
    application layer (today there isn't).

    Naming convention (per 6f-2 gate review): gerund / adjective
    for the active steady-state (matches ISA-88 / PackML's
    `Execute` and Bluesky's `running`); past-participle for
    pause-state and terminals (`Held`, `Completed`, `Aborted`,
    `Stopped`) consistent with our own Subject precedent.

    Enum values are PascalCase strings (matches BC-map status
    vocabulary; log lines and DTOs read naturally without mapping).
    """

    RUNNING = "Running"
    HELD = "Held"
    COMPLETED = "Completed"
    ABORTED = "Aborted"
    STOPPED = "Stopped"
    TRUNCATED = "Truncated"


class InvalidRunNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Run name must be 1-{RUN_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class RunAlreadyExistsError(Exception):
    """Attempted to start a run whose stream already has events."""

    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"Run {run_id} already exists")
        self.run_id = run_id


class RunNotFoundError(Exception):
    """Attempted an operation on a run whose stream has no events."""

    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"Run {run_id} not found")
        self.run_id = run_id


class RunBoundPlanDeprecatedError(Exception):
    """Attempted to start a Run against a Deprecated Plan.

    Plan deprecation is advisory at the Plan-aggregate layer (Plan
    itself doesn't reject operations on Deprecated state), but
    Run-start rejects — you can't execute a tombstoned Plan.
    Mapped to HTTP 409.

    Symmetric to Plan-bind's PlanBoundPracticeDeprecatedError /
    PlanBoundMethodDeprecatedError pattern.
    """

    def __init__(self, plan_id: UUID) -> None:
        super().__init__(f"Cannot start Run against Plan {plan_id}: Plan is Deprecated")
        self.plan_id = plan_id


class RunSubjectNotMountableError(Exception):
    """Attempted to start a Run against a Subject not in Mounted | Measured.

    Subject-state precondition for Run-start (gate-review Q6):
    Subject must be in `Mounted` (sample on stage, ready) or
    `Measured` (re-measurement of a previously-measured subject).
    Other states (Received, Removed, Returned, Stored, Discarded)
    don't make sense for a new Run binding.

    Mapped to HTTP 409.
    """

    def __init__(self, subject_id: UUID, current_status: str) -> None:
        super().__init__(
            f"Cannot start Run against Subject {subject_id}: currently in "
            f"status {current_status}, Run-start requires Mounted or Measured"
        )
        self.subject_id = subject_id
        self.current_status = current_status


class RunPlanAssetDecommissionedError(Exception):
    """Plan's bound Assets include one or more Decommissioned at Run-start.

    Re-validation of Asset state at Run-start (NOT just Plan-bind
    snapshot). If an Asset got decommissioned between Plan-bind and
    Run-start, the Run can't proceed against the now-tombstoned
    Asset. Mapped to HTTP 409.

    Mirrors Plan-bind's PlanAssetDecommissionedError shape.
    """

    def __init__(self, asset_ids: list[UUID]) -> None:
        super().__init__(
            f"Cannot start Run: the following Assets bound by the Plan are "
            f"Decommissioned: {[str(a) for a in asset_ids]}"
        )
        self.asset_ids = asset_ids


# hoist alias: `InvalidRunExternalRefError` is the cross-BC
# `InvalidIdentifierError` from `cora.shared.identifier`.
# Kept as a Run-scoped alias so the BC's routes / tools / re-exports
# (which name the symbol `InvalidRunExternalRefError`) stay unchanged.
# `isinstance(exc, InvalidRunExternalRefError)` and
# `isinstance(exc, InvalidIdentifierError)` are now equivalent.
InvalidRunExternalRefError = InvalidIdentifierError


class RunCannotJoinCampaignError(Exception):
    """Attempted to start a Run against a Campaign in a non-membership-eligible status.

    Cross-BC gate: when `StartRun.campaign_id` is provided
    the handler pre-loads the Campaign and the decider verifies its
    status is in `{Planned, Active, Held}` (the membership-eligible
    set). Closed and Abandoned Campaigns refuse new members
    (membership locked at terminal per the design memo lock).

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, campaign_id: UUID, campaign_status: str) -> None:
        super().__init__(
            f"Run {run_id} cannot join Campaign {campaign_id}: Campaign is in "
            f"status {campaign_status}; membership requires Planned, Active, "
            f"or Held."
        )
        self.run_id = run_id
        self.campaign_id = campaign_id
        self.campaign_status = campaign_status


class RunAlreadyAssignedToCampaignError(Exception):
    """Attempted to add a Run already assigned to a (different) Campaign.

    Invariant: a Run participates in at most one Campaign
    at a time. The cross-aggregate `add_run_to_campaign` slice refuses
    when the loaded Run already carries a non-None `campaign_id` that
    differs from the requested target Campaign. Removing the Run from
    its current Campaign first is the operator's remediation path.

    Mapped to HTTP 409.
    """

    def __init__(
        self,
        run_id: UUID,
        existing_campaign_id: UUID,
        new_campaign_id: UUID,
    ) -> None:
        super().__init__(
            f"Run {run_id} is already assigned to Campaign "
            f"{existing_campaign_id}; cannot add to Campaign {new_campaign_id} "
            f"without first removing from the current Campaign."
        )
        self.run_id = run_id
        self.existing_campaign_id = existing_campaign_id
        self.new_campaign_id = new_campaign_id


class RunRequiresActiveClearanceError(Exception):
    """No Safety clearance references this Run's scope at all.

    Cross-BC gate: `start_run` requires at least ONE Active Safety
    Clearance whose bindings cover the Run's
    `(run_id, subject_id, asset_ids)`. This error fires when ZERO
    clearances reference any of these — operator must
    `register_clearance` + walk it to Active first.

    Distinct from `RunClearanceCoverageMismatchError`, which fires
    when clearances DO reference the Run's scope but none are in
    Active status. Two errors so operator-facing messaging can
    distinguish "no clearance" vs "clearance exists but inactive".
    """

    def __init__(self, run_id: UUID) -> None:
        super().__init__(
            f"Run {run_id} cannot start: no Safety clearance references this "
            f"Run / its Subject / its bound Assets. Register and activate a "
            f"clearance with a matching binding before starting the run."
        )
        self.run_id = run_id


class RunClearanceCoverageMismatchError(Exception):
    """Clearances reference this Run's scope but none are Active.

    Cross-BC gate: clearances exist referencing the Run's
    `(run_id, subject_id, asset_ids)` but their statuses are all
    non-Active (Defined / Submitted / UnderReview / Approved / Expired
    / Rejected / Superseded). Operator must walk a referencing
    clearance to Active (or amend a Superseded one) before starting
    the run.
    """

    def __init__(self, run_id: UUID, *, referencing_clearance_count: int) -> None:
        super().__init__(
            f"Run {run_id} cannot start: {referencing_clearance_count} "
            f"clearance(s) reference this Run's scope but none are Active. "
            f"Walk one to Active (or amend a Superseded one) before starting."
        )
        self.run_id = run_id
        self.referencing_clearance_count = referencing_clearance_count


class RunCapabilitiesNotSatisfiedError(Exception):
    """Plan's Method needs capabilities not currently provided by bound Assets.

    Re-validation at Run-start: the bound Asset capability set
    can drift after Plan-bind (operators add/remove capabilities,
    decommission assets and replace with substitutes, etc.).
    Run-start re-checks the capability superset against current
    Asset state. Mapped to HTTP 409.

    Mirrors Plan-bind's PlanFamiliesNotSatisfiedError shape.
    """

    def __init__(self, missing_family_ids: frozenset[UUID]) -> None:
        super().__init__(
            f"Run capabilities not satisfied at start time: bound Assets "
            f"are missing capabilities "
            f"{sorted(str(c) for c in missing_family_ids)}"
        )
        self.missing_family_ids = missing_family_ids


class RunRequiresAvailableSupplyError(Exception):
    """No Supply registered for one of the Method.needed_supplies kinds.

    Cross-BC gate: `start_run` requires that for every kind in the
    governing Method's `needed_supplies`, at least one non-Decommissioned
    Supply is registered. This error fires when ZERO Supplies of a
    required kind are registered. Operator must `register_supply` for
    the missing kind first.

    Distinct from `RunSupplyCoverageMismatchError`, which fires when
    Supplies of the required kind ARE registered but all are in
    non-Available status. Two errors so operator-facing messaging can
    distinguish "no Supply at all" vs "Supply exists but unavailable".
    Mirrors the `RunRequiresActiveClearanceError` / `RunClearanceCoverageMismatchError`
    pair shape; same Requires-then-CoverageMismatch convention.
    Mapped to HTTP 409 per [[project_supply_preflight_gate_design]].
    """

    def __init__(self, run_id: UUID, kind: str) -> None:
        super().__init__(
            f"Run {run_id} cannot start: no Supply registered for required kind {kind!r}. "
            f"Register a Supply of that kind and mark it Available before starting."
        )
        self.run_id = run_id
        self.kind = kind


class RunSupplyCoverageMismatchError(Exception):
    """Supply registered for the required kind but none are Available.

    Cross-BC gate: at least one Supply of the required kind is
    registered (and not Decommissioned), but all have status in
    {Unknown, Degraded, Unavailable, Recovering}. Operator must mark
    one Available (e.g., walk down the resource and issue
    `mark_supply_available` or `restore_supply`) before starting.

    `supply_status_summary` carries `(supply_id, status)` tuples for
    every Supply of the required kind so the 409 message can name the
    specific Supplies blocking the start. Mirrors the sibling
    `RunClearanceCoverageMismatchError` pair shape.
    Mapped to HTTP 409 per [[project_supply_preflight_gate_design]].
    """

    def __init__(
        self,
        run_id: UUID,
        kind: str,
        supply_status_summary: frozenset[tuple[UUID, str]],
    ) -> None:
        summary_sorted = sorted((str(sid), st) for sid, st in supply_status_summary)
        super().__init__(
            f"Run {run_id} cannot start: required kind {kind!r} has no "
            f"Available Supply. Current statuses: {summary_sorted}. "
            f"Mark one Available before starting."
        )
        self.run_id = run_id
        self.kind = kind
        self.supply_status_summary = supply_status_summary


class RunRequiresPermittedEnclosureError(Exception):
    """A referencing Enclosure is not currently Permitted-and-Active.

    Cross-BC gate: `start_run` derives the set of referencing
    Enclosures by walking `EnclosureLookup.find_for_assets` against
    the Run's `scoped_asset_ids`. Per L-pre-1 (always-derive-from-
    Asset-chain), Methods do NOT declare an explicit needed-enclosure
    list; the chain IS the declaration. This error fires when EVERY
    referencing Enclosure is in `permit_status != "Permitted"` OR
    `lifecycle != "Active"` (the "universally not permitted" branch
    of the two-error pair). When at least one row passes and at
    least one fails, the mixed-status case, the decider raises the
    sibling `RunEnclosureCoverageMismatchError` instead. Empty
    referencing rows is Permit-by-default: neither error fires.

    `enclosure_status_summary` carries `(enclosure_id, label)` tuples
    where `label` is the joined `permit_status|lifecycle` string for
    every failing Enclosure so the 409 message can name each one. An
    Asset with NO referencing Enclosure rows is Permit-by-default
    (per the port docstring) and never raises this error.

    Sibling of `RunRequiresAvailableSupplyError` /
    `RunSupplyCoverageMismatchError`. Mapped to HTTP 409 per
    [[project_enclosure_stage1_design]].
    """

    def __init__(
        self,
        run_id: UUID,
        enclosure_status_summary: frozenset[tuple[UUID, str]],
    ) -> None:
        summary_sorted = sorted((str(eid), label) for eid, label in enclosure_status_summary)
        super().__init__(
            f"Run {run_id} cannot start: one or more referencing Enclosures "
            f"are not Permitted-and-Active. Current statuses: {summary_sorted}. "
            f"Walk each Enclosure to Permitted (and keep it Active) before starting."
        )
        self.run_id = run_id
        self.enclosure_status_summary = enclosure_status_summary


class RunEnclosureCoverageMismatchError(Exception):
    """Some referencing Enclosure rows resolved but coverage is incomplete.

    Cross-BC gate sibling to `RunRequiresPermittedEnclosureError`,
    the mixed-status branch of the two-error pair: this error fires
    when at least one referencing Enclosure passes the
    Permitted-and-Active check AND at least one OTHER row fails it.

    The sibling `Requires` error covers the universally-not-permitted
    branch (every row failed). Empty referencing rows is Permit-by-
    default and never raises either error. Two error classes so
    operator-facing messaging can distinguish "everything is wrong"
    (rebuild the whole chain) from "a subset is wrong" (walk just
    the failing rows to Permitted). Mapped to HTTP 409.
    """

    def __init__(
        self,
        run_id: UUID,
        enclosure_status_summary: frozenset[tuple[UUID, str]],
    ) -> None:
        summary_sorted = sorted((str(eid), label) for eid, label in enclosure_status_summary)
        super().__init__(
            f"Run {run_id} cannot start: referencing Enclosure(s) failed the "
            f"Permitted-and-Active gate. Current statuses: {summary_sorted}. "
            f"Walk each Enclosure to Permitted before starting."
        )
        self.run_id = run_id
        self.enclosure_status_summary = enclosure_status_summary


class RunCannotCompleteError(Exception):
    """Attempted to complete a Run not in `Running`.

    Single-source guard: `complete_run` accepts only `Running`.
    Re-completing an already-`Completed` Run raises (strict-not-
    idempotent); completing an `Aborted` / `Stopped` Run raises;
    completing a `Held` Run raises (gate-review 6f-3 Q1 lock —
    completion claims active achievement, so it requires the Run
    to be actively running; an operator wanting to complete a held
    run must Resume → Complete).

    Per-transition error class — same naming convention as
    `PlanCannotDeprecateError` / `MethodCannotVersionError`.
    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be completed: currently in status "
            f"{current_status.value}, complete requires "
            f"{RunStatus.RUNNING.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class RunCannotAbortError(Exception):
    """Attempted to abort a Run not in `Running` or `Held`.

    Multi-source guard: `abort_run` accepts `Running | Held`.
    Emergencies during a hold are real — operators can't be
    forced to first resume just to abort. Aborting an already-
    terminal Run (Completed | Aborted | Stopped) raises;
    re-aborting an `Aborted` Run raises (strict-not-idempotent).

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be aborted: currently in status "
            f"{current_status.value}, abort requires "
            f"{RunStatus.RUNNING.value} or {RunStatus.HELD.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class RunCannotHoldError(Exception):
    """Attempted to hold a Run not in `Running`.

    Single-source guard: `hold_run` accepts only `Running`.
    Re-holding an already-`Held` Run raises (strict-not-
    idempotent); holding a terminal Run raises.

    Hold/Resume is bidirectional and unlimited-cycle (PackML +
    Bluesky precedent), so an operator can hold → resume → hold
    repeatedly during a single Run; each hold requires an
    intervening resume.

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be held: currently in status "
            f"{current_status.value}, hold requires "
            f"{RunStatus.RUNNING.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class RunCannotResumeError(Exception):
    """Attempted to resume a Run not in `Held`.

    Single-source guard: `resume_run` accepts only `Held`. The
    inverse of hold (which requires `Running`). Resuming an
    already-`Running` Run raises (strict-not-idempotent);
    resuming a terminal Run raises.

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be resumed: currently in status "
            f"{current_status.value}, resume requires "
            f"{RunStatus.HELD.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class RunCannotStopError(Exception):
    """Attempted to stop a Run not in `Running` or `Held`.

    Multi-source guard: `stop_run` accepts `Running | Held`.
    Symmetric with abort_run's source set, operator-initiated
    controlled exits don't require an active state, only any
    non-terminal state. Stopping a terminal Run raises.

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be stopped: currently in status "
            f"{current_status.value}, stop requires "
            f"{RunStatus.RUNNING.value} or {RunStatus.HELD.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class RunCannotTruncateError(Exception):
    """Attempted to truncate a Run not in `Running` or `Held`.

    Multi-source guard: `truncate_run` accepts `Running | Held`.
    Same source set as stop / abort, every operator-initiated
    terminal accepts any non-terminal state. Truncating a Run that
    has already reached a terminal (Completed | Aborted | Stopped |
    Truncated) raises; re-truncating a `Truncated` Run raises
    (strict-not-idempotent, matches the other terminals).

    Truncated and Stopped are both operator-initiated, but they are
    semantically distinct: Stopped is a controlled exit while the
    system is still responsive; Truncated is the cleanup mechanism
    for a Run that became de-facto dead through interruption (power
    loss, process crash, hardware fault) and is being closed
    retroactively. The current_status field will typically still be
    Running (the FSM never observed the interruption) when
    truncate is called.

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be truncated: currently in status "
            f"{current_status.value}, truncate requires "
            f"{RunStatus.RUNNING.value} or {RunStatus.HELD.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class InvalidRunAbortReasonError(ValueError):
    """The supplied abort reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error so direct in-process
    callers (sagas, tests) get the same protection. Same precedent as
    `InvalidPlanVersionTagError` / `InvalidPracticeVersionTagError`.

    Free-form `str` (1-500 chars) is the locked 6f-2 design (gate-
    review Q2). Structured taxonomy is future-additive when the
    documented re-evaluation triggers fire:
      - vocabulary convergence across ≥10 real aborts;
      - Decision BC adopts RunAbort with structured-context queries;
      - compliance/audit demand for categorical reason tracking.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Run abort reason must be 1-{REASON_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class RunAbortReason:
    """Free-form abort reason. Trimmed; 1-500 chars.

    Domain VO (not just `str`) so the decider validates uniformly
    via the shared `validate_bounded_text` helper (same trimming + bounded-
    length contract as the 11 BoundedName VOs). The on-the-wire
    representation in `RunAborted.reason` is `str` (post-trim) for
    payload simplicity; the VO exists at decider-input time only.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidRunAbortReasonError,
        )
        object.__setattr__(self, "value", trimmed)


class InvalidRunStopReasonError(ValueError):
    """The supplied stop reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error. Sibling of
    `InvalidRunAbortReasonError`; kept as a separate class so API
    error responses unambiguously identify which transition the
    invalid reason was for.

    Free-form `str` (1-500 chars) is the locked 6f-3 design (gate-
    review Q2). Same future-additive structured-taxonomy posture
    as `RunAborted.reason` — the three documented re-evaluation
    triggers for abort apply equally to stop:
      - vocabulary convergence across ≥10 real stops;
      - Decision BC adopts RunStop with structured-context queries;
      - compliance/audit demand for categorical reason tracking.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Run stop reason must be 1-{REASON_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class RunStopReason:
    """Free-form stop reason. Trimmed; 1-500 chars.

    Sibling of `RunAbortReason`, identical pattern, distinct
    error class for clearer API error responses. The on-the-wire
    representation in `RunStopped.reason` is `str` (post-trim)
    for payload simplicity; the VO exists at decider-input time
    only.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidRunStopReasonError,
        )
        object.__setattr__(self, "value", trimmed)


class InvalidRunTruncateReasonError(ValueError):
    """The supplied truncate reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error. Sibling of
    `InvalidRunStopReasonError`; kept as a separate class so API
    error responses unambiguously identify which transition the
    invalid reason was for.

    Free-form `str` (1-500 chars) is the locked 6f-4 design (gate-
    review L8 + stress-test confirmation). Same future-additive
    structured-taxonomy posture as `RunAborted.reason` /
    `RunStopped.reason`, the same three documented re-evaluation
    triggers apply:
      - vocabulary convergence across >=10 real truncations;
      - Decision BC adopts RunTruncate with structured-context queries;
      - compliance/audit demand for categorical reason tracking.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Run truncate reason must be 1-{REASON_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class InvalidRunInterruptedAtError(ValueError):
    """The supplied truncate `interrupted_at` is in the future relative to `now`.

    `interrupted_at` is the operator's best guess at when the
    actual interruption happened, separate from `occurred_at`
    (when the truncate command was processed). The two timestamps
    can be hours or days apart for weekend / overnight
    interruptions, but `interrupted_at` MUST not be later than
    `now`, you cannot have been interrupted in the future.

    Validated defensively at the decider via this error so direct
    in-process callers (sagas, tests) get the same protection as
    HTTP / MCP callers. The API surface does not pre-validate
    against `now` (Pydantic Field has no relative-bound primitive),
    only the absolute schema (datetime parse + tz-aware), so this
    decider check is the one source of truth.

    Mapped to HTTP 400.
    """

    def __init__(self, interrupted_at: datetime, now: datetime) -> None:
        super().__init__(
            f"Run truncate interrupted_at {interrupted_at.isoformat()} is in the future "
            f"(now is {now.isoformat()}); the interruption cannot have happened later than "
            f"the truncate command itself"
        )
        self.interrupted_at = interrupted_at
        self.now = now


@dataclass(frozen=True)
class RunTruncateReason:
    """Free-form truncate reason. Trimmed; 1-500 chars.

    Sibling of `RunStopReason` and `RunAbortReason`. The on-the-
    wire representation in `RunTruncated.reason` is `str` (post-
    trim); the VO exists at decider-input time only.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidRunTruncateReasonError,
        )
        object.__setattr__(self, "value", trimmed)


class InvalidChannelNameError(ValueError):
    """The supplied observation channel_name is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the handler via the `ChannelName` VO so direct
    in-process callers (sagas, tests) get the same protection. Same
    pattern as `InvalidRunNameError`.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Reading channel_name must be 1-{READING_CHANNEL_NAME_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class InvalidObservationValueError(ValueError):
    """The supplied observation value is NaN or Infinity.

    Pydantic catches this at the API boundary via `allow_inf_nan=False`;
    this error class exists for direct in-process callers (sagas, tests)
    that bypass Pydantic. The Postgres adapter ALSO enforces the guard
    via a CHECK constraint, providing defense-in-depth.

    Mapped to HTTP 400.
    """

    def __init__(self, value: float) -> None:
        super().__init__(
            f"Reading value must be finite (got: {value!r}; NaN and Infinity rejected)"
        )
        self.value = value


class InvalidSamplingProcedureError(ValueError):
    """The supplied sampling_procedure is not in the allowed set.

    Pydantic catches this at the API boundary via `Literal[...]`;
    this error class exists for direct in-process callers that bypass
    Pydantic. Allowed values evolve: 6f-5b ships {"baseline"};
    6f-5c extends to {"baseline", "monitor"}; future values land
    additively without a migration (the column is plain TEXT).

    Mapped to HTTP 400.
    """

    def __init__(self, value: str, allowed: frozenset[str]) -> None:
        super().__init__(
            f"Reading sampling_procedure {value!r} not in allowed set {sorted(allowed)!r}"
        )
        self.value = value
        self.allowed = allowed


class RunObservationLogbookClosedError(Exception):
    """Attempted to append an observation to a Run in a terminal state.

    The Run's terminal status (Completed | Aborted | Stopped | Truncated)
    implicitly closes the observation logbook: post-terminal observations are
    rejected. There is no separate `RunObservationLogbookClosed` event today;
    Run.status is the close signal (see [[project_run_reading_design]]
    §Decision for the lazy-open + status-as-close-signal rationale).

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} observation logbook is closed: Run is in terminal "
            f"status {current_status.value}; observations can only be appended "
            f"while Run is in {RunStatus.RUNNING.value} or {RunStatus.HELD.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


@bounded_name(
    max_length=READING_CHANNEL_NAME_MAX_LENGTH,
    error_class=InvalidChannelNameError,
)
@dataclass(frozen=True)
class ChannelName:
    """Sensor or motor identifier on a Observation entry. Trimmed; 1-255 chars.

    Operator-meaningful free-form string (for example `T_sample`,
    `motor_x`, `ring_current`). No regex or vocabulary constraint
    (signal_type / channel naming conventions are pilot-specific and
    will settle over time, mirroring AssetPort.signal_type's free-form
    posture).
    """

    value: str


@bounded_name(
    max_length=RUN_NAME_MAX_LENGTH,
    error_class=InvalidRunNameError,
)
@dataclass(frozen=True)
class RunName:
    """Display name for a run. Trimmed; 1-200 chars.

    Eleventh occurrence of the trimmed-bounded-name VO pattern.
    Uses the shared `validate_bounded_text` helper hoisted at the
    rule-of-three trigger (see `cora.shared.bounded_text`).
    """

    value: str


# Open-scheme anti-corruption ref: `Identifier(scheme, value)` lives at
# `cora.shared.identifier`. The Run BC carries
# `external_refs: frozenset[Identifier]` on Run state; imports come
# from the infrastructure module directly.


@dataclass(frozen=True)
class Run:
    """Aggregate root: one execution instance.

    `plan_id` is the Plan being executed (eventual-consistency ref;
    loaded at handler-load time for re-validation, NOT verified by
    the decider as opaque). `subject_id` is the Subject being
    measured, or None for calibration / dark-field runs. `raid` is
    the Research Activity Identifier (ISO 23527) for the project
    this Run belongs to, opaque string carried verbatim, defaults
    to None (additive retrofit; legacy Runs fold with raid=None
    because old RunStarted payloads have no raid key). `status`
    defaults to `Running` — the active steady-state.

    `override_parameters` is the operator-supplied overrides on top
    of `Plan.default_parameters` (RFC 7396 merge).
    `effective_parameters` is the post-merge resolved snapshot
    (defaults + overrides) that governed this Run. Both default to
    `{}` for legacy streams without the keys (additive-state pattern;
    forward-compat via `payload.get(..., {})` in `from_stored`).
    Mirrors Bluesky start-document / MLflow run.params / W&B
    run.config / ISA-88 control-recipe / RO-Crate CreateAction
    convention: the run carries the resolved parameter set as a
    first-class read surface (researched 2026-05-14;
    [[project_run_parameters_design]] §6g-c).

    `trigger_source` is operator-supplied free text
    capturing what initiated this Run (operator-manual, scheduler,
    prior-run, automation). Optional. Future Decision-BC integration
    may populate this from `Inference.entries` references.
    """

    id: UUID
    name: RunName
    plan_id: UUID
    subject_id: UUID | None
    raid: str | None = None
    status: RunStatus = RunStatus.RUNNING
    override_parameters: dict[str, Any] = field(default_factory=dict[str, Any])
    effective_parameters: dict[str, Any] = field(default_factory=dict[str, Any])
    trigger_source: str | None = None
    # lazily populated when first observation is appended
    # (RunObservationLogbookOpened event sets this field). None on Runs
    # that never recorded observations; legacy streams without the field fold
    # cleanly with this default. See [[project_run_reading_design]]
    # for the lazy-open rationale.
    observation_logbook_id: UUID | None = None
    # anti-corruption refs to upstream-deferred concepts
    # CORA does NOT model as aggregates (proposal / btr / lab_visit /
    # session). Mirrors Safety BC's ExternalBinding shape. Populated at
    # register time from StartRun.external_refs; legacy Runs without
    # the field fold cleanly via `payload.get("external_refs", [])`.
    # ExternalBinding-based clearance coverage gating is deferred per
    # [[project_safety_clearance_design]] watch item; today the
    # field is forward-compat only (gate uses Run/Subject/Asset bindings).
    external_refs: frozenset[Identifier] = field(default_factory=frozenset[Identifier])
    # optional Campaign membership. None means the Run is
    # standalone (not part of any Campaign). Set on RunStarted (when
    # `StartRun.campaign_id` was provided) or via the post-hoc
    # `add_run_to_campaign` slice (RunAddedToCampaign event); cleared
    # by `remove_run_from_campaign` (RunRemovedFromCampaign event). One
    # Campaign per Run invariant: never N (per
    # [[project_campaign_design]] lock). Forward-compat additive field;
    # legacy streams without the field fold via `payload.get("campaign_id")`
    # returning None.
    campaign_id: UUID | None = None
    # mid-flight parameter steering denorm. `last_adjusted_at`
    # carries the occurred_at of the most recent `RunAdjusted` event;
    # `last_adjusted_by` carries the ActorId of the principal who
    # issued that adjust (overwrite-on-each-adjust per the fold-
    # symmetry pair-rule; see [[project_fold_symmetry_design]]).
    # `adjustment_count` is the cumulative count of accepted adjust
    # operations. Defaults to None / None / 0 so legacy streams without
    # the fields fold cleanly (forward-compat additive-state pattern,
    # mirrors observation_logbook_id / campaign_id precedent). Per-
    # adjustment audit history lives on the event log; aggregate state
    # stays slim.
    last_adjusted_at: datetime | None = None
    last_adjusted_by: ActorId | None = None
    adjustment_count: int = 0
    # AsShot calibration pin set (Calibration BC integration
    # per [[project_calibration_design]]). Each entry is a
    # CalibrationRevision.id that was live at start_run time.
    # IMMUTABLE after start_run by aggregate-level invariant — every
    # transition arm in the evolver (RunHeld / RunResumed /
    # RunCompleted / RunAborted / RunStopped / RunTruncated /
    # RunAdjusted / RunAddedToCampaign / RunRemovedFromCampaign /
    # RunObservationLogbookOpened) preserves `prior.pinned_calibration_ids`
    # verbatim. The AsShot anchor lets downstream consumers (Dataset
    # reconstruction in the Data BC, RunDebriefer AI advisories) answer "what
    # calibration was this scan acquired against?" deterministically
    # months later, even if later refined revisions arrive on the
    # same Calibration aggregate. DNG AsShot vs Current precedent
    # (Q5/Q6 research). Defaults to empty frozenset so legacy streams
    # without the field fold cleanly via `payload.get("pinned_calibration_ids", [])`.
    pinned_calibration_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])


class InvalidRunParametersError(ValueError):
    """The supplied Run effective_parameters (defaults + overrides) failed
    validation against the owning Method's parameters_schema.

    Strict when Method.parameters_schema is None: non-empty effective
    parameters are rejected (Method declares no contract; operators
    wanting parameter-less Methods declare `parameters_schema={}`
    explicitly). When the schema IS declared, the merged dict must
    conform per jsonschema-rs Draft 2020-12. Mirrors
    `InvalidPlanDefaultParametersError` shape and the
    "no Capabilities + non-empty settings → reject" cross-BC anchor.
    Mapped to HTTP 400 by the run BC's exception handler.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Run parameters: {reason}")
        self.reason = reason


class RunCannotAdjustError(Exception):
    """Attempted to adjust a Run not in `Running` or `Held`.

    Multi-source guard: `adjust_run` accepts `Running | Held`. Idle /
    Starting use `override_parameters` at start time; terminal states
    (Completed / Aborted / Stopped / Truncated) are by definition
    frozen.

    Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID, current_status: "RunStatus") -> None:
        super().__init__(
            f"Run {run_id} cannot be adjusted: currently in status "
            f"{current_status.value}, adjust requires "
            f"{RunStatus.RUNNING.value} or {RunStatus.HELD.value}"
        )
        self.run_id = run_id
        self.current_status = current_status


class InvalidRunAdjustPatchError(ValueError):
    """The supplied `parameters_patch` is empty or otherwise unusable.

    Empty patches are rejected at the decider so the audit log never
    carries a no-op "operator adjusted with no change" entry. The API
    boundary validates the dict shape via Pydantic; this error class
    catches the semantic (non-empty) check.

    Mapped to HTTP 400.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid run adjust patch: {reason}")
        self.reason = reason


class InvalidRunAdjustSchemaError(ValueError):
    """The post-merge `effective_parameters` failed validation against
    the owning Method's `parameters_schema`.

    Sibling of `InvalidRunParametersError` (raised by `start_run`).
    Kept as a distinct error class so API responses
    unambiguously identify the adjust path. RELAXED-by-design for
    schemaless Methods: when Method.parameters_schema is None the
    decider skips validation (an adjustment to a schemaless Method
    is operator-responsibility territory; see
    `validate_adjusted_parameters_against_method_schema`).

    Mapped to HTTP 400.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(f"Invalid run adjust after merge: {detail}")
        self.detail = detail


class InvalidRunAdjustReasonError(ValueError):
    """The supplied adjust reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider so direct in-process callers
    (sagas, tests) get the same protection. Sibling of
    `InvalidRunAbortReasonError` / `InvalidRunStopReasonError` /
    `InvalidRunTruncateReasonError`; distinct class so API responses
    unambiguously identify the adjust path.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Run adjust reason must be 1-{REASON_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidPinnedCalibrationsError(ValueError):
    """The supplied pinned_calibration_ids set has too many entries.

    Per-entry validation (each is a UUID) is type-enforced; the
    set-cardinality cap protects against accidentally massive AsShot-
    pin payloads on a single Run start. Mirrors Data BC's
    `InvalidUsedCalibrationsError` shape exactly (same precedent +
    same default cap of 64). Validated at the decider; the API
    boundary also enforces `max_length` via Pydantic for fast 422
    failures on obviously-malformed input.

    NO cross-BC existence check on the cited revision ids per
    [[project_calibration_design]] anti-hook #3 (revision-cited
    atomic-ID model) + canonical DDD eventual-consistency stance on
    cross-aggregate rules (Vernon/Evans). Symmetric to Data BC's
    register_dataset decider-time treatment.

    Mapped to HTTP 400.
    """

    def __init__(self, count: int) -> None:
        super().__init__(
            f"Run pinned_calibration_ids must have at most "
            f"{RUN_PINNED_CALIBRATIONS_MAX_ENTRIES} entries (got: {count})"
        )
        self.count = count


def validate_pinned_calibration_ids(value: frozenset[UUID]) -> frozenset[UUID]:
    """Normalize / validate pinned_calibration_ids for the Run state and decider.

    Cardinality-only check. NO per-element existence
    check (revision-cited atomic-ID model; cross-BC eventual-
    consistency per [[project_calibration_design]] anti-hook #3 +
    Vernon/Evans DDD canon). Mirrors Data BC's
    `validate_used_calibration_ids` exactly — same shape, same default
    cap, same justification.
    """
    if len(value) > RUN_PINNED_CALIBRATIONS_MAX_ENTRIES:
        raise InvalidPinnedCalibrationsError(len(value))
    return value
