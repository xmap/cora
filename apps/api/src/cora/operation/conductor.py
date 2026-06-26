"""Operation BC `Conductor`: walks Procedure steps via ControlPort + actions + checks.

The Conductor is the Operation BC's Layer-2 runtime per
[[project_edge_runtime_design]]. It receives a sequence of `Step`
operations (a discriminated union; the arms are pinned against the
Procedure aggregate's `STEP_KIND_VALUES`), dispatches each through the
right primitive (`ControlPort.write` for setpoints, an action body
looked up in the `ActionRegistry` for actions, `ControlPort.read`
followed by criterion evaluation for checks + captures, and
`ComputePort.submit` for a compute step), and records every outcome as a
step entry in the Procedure's steps logbook via the existing
`append_activities` handler.

The Conductor is a single-process asyncio walker; per-call state
lives on the returned `ConductorResult`. Substrate-agnostic on the
setpoint + check paths (address parses inside the routed
`ControlPort` adapter); body-agnostic on the action path (the
registry maps a free-form name to a callable the deployment
supplies).

## Failure mode

The first step that raises any `Control*Error`, first action whose
name is not registered, OR first check whose criterion did not match
(or whose reading was non-Good quality) halts execution. The failing
step IS recorded in the logbook (payload's `result="failed"` +
`error_class` + `message`) before the call returns; subsequent steps
are NOT attempted. The Procedure's FSM is NOT advanced by the
Conductor; the caller decides abort vs retry vs hand-off after
inspecting `ConductorResult.failure`.

Non-`Control*Error` exceptions raised by an action body (programmer
errors, `KeyboardInterrupt`, `CancelledError`, third-party-library
crashes) are NOT caught: they propagate to the caller so signals +
cancellation behave normally and bugs surface. Action bodies that
want to signal a domain-level "this didn't work out" without throwing
can return a result dict carrying their own status (e.g. `{"ok":
False, "reason": "out_of_range"}`); the Conductor treats any return
from a body as success-shaped at this tier.

## Resume (execute_from)

`execute_from` replays the PINNED resolved step list from a re-establishment
boundary rather than re-deriving the step list: re-drive setpoints, re-run
checks as fresh gates, and halt-for-operator on an acquisition
(`ActionStep`). It is the Tier-1 resumable-conduct primitive
([[project_resumable_conduct_design]]); the step list comes from
`ResolvedStepsRecorded` parsed via `steps_from_payload`. Like `execute`
it drives no FSM transition.

## Pre-effect in-flight marker (side-effecting steps)

A setpoint and an action are side-effecting: each records a SEPARATE
`result="in_flight"` step entry BEFORE the effect runs, then the
`ok` / `failed` outcome entry after. This doubles the per-step append
count for those two kinds. A check is a pure read (always safe to
re-run), so it records no marker, only its single outcome entry. The
marker is the resume substrate: an `in_flight` entry with no matching
outcome for the same `step_index` is the one step that was mid-flight
when a conduct halted, even if the halt was a crash or cancellation
(the marker append completes before the effect). See
[[project_resumable_conduct_design]] Tier 1.

## Check semantics

A `CheckStep` carries an address + an acceptance criterion. The
Conductor reads from the address via `ControlPort.read`, requires
`Measurement.quality == "Good"` (Uncertain or Bad fails the check), and
evaluates the criterion against the observed value. The closed
criterion union (`EqualsCriterion | WithinToleranceCriterion`) keeps the wire shape
JSON-clean while leaving room for future variants (`OneOf`,
`Matches`, `Within` range) to land as additive code edits without a
migration. Non-numeric values land in `WithinToleranceCriterion` as a clean
mismatch (no coercion exception escapes); criterion handling tolerates
substrate value-type drift.

## Cancellation handling

`execute()` lets `CancelledError` propagate untouched: it is the
lower-level primitive that does not own FSM transitions. `conduct()`
catches `CancelledError` raised mid-`execute`, attempts a best-effort
`abort_procedure(reason="cancelled mid-execute")` so the Procedure
FSM lands in Aborted rather than orphaned in Running, then re-raises
so the caller's task still sees the cancellation. Cancellation
during the start / complete handler calls themselves propagates as-is
(those boundaries are single-handler-atomic; abort cleanup would race
the in-flight transition).

## Out of scope at this iteration

The executor arc continues; the following land in subsequent iters:

  - pre-write reading capture (`verify` only does post-write today;
    a `capture_pre` flag would land additively when an undo / rollback
    pattern surfaces)
  - additional check criteria (`OneOf`, `Matches`, `Within` range)
  - concurrent / pipelined setpoint dispatch (sequential at v1)
  - `Capability`-driven step-list resolution (caller supplies the list)
  - action-body discovery from disk / config (registry is hand-built today)
  - acceptance of Uncertain quality (today only Good passes; an opt-in
    `allowed_qualities` field on CheckStep would land additively)

## Why call the handler not the store directly

`append_activities` is the slice handler that owns lazy-open of
the steps logbook + status guard (Procedure must be `Running`) +
authorization. The Conductor calls the handler, not the underlying
`ActivityStore`, so those concerns stay caged inside the existing slice
and the Conductor stays a thin orchestrator. The dependency is the
handler's `Handler` Protocol, not a concrete binding, so tests inject
a fake without standing up the full handler machinery.
"""

import contextlib
import math
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Protocol, cast
from uuid import UUID

from cora.infrastructure.edge_runtime import abort_orphan_on_cancel
from cora.infrastructure.ports.clock import Clock
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.ports.id_generator import IdGenerator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._control_dispatch_context import with_dispatch_correlation_id
from cora.operation.aggregates.procedure import (
    ProcedureIterationLimitReachedError,
    ProcedureNotFoundError,
    merge_actuation_kinds,
)
from cora.operation.errors import CheckFailedError, UnauthorizedError, UnknownActionError
from cora.operation.features.abort_procedure.command import AbortProcedure
from cora.operation.features.abort_procedure.handler import Handler as AbortProcedureHandler
from cora.operation.features.append_activities.command import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities.handler import (
    Handler as AppendProcedureActivitiesHandler,
)
from cora.operation.features.complete_procedure.command import CompleteProcedure
from cora.operation.features.complete_procedure.handler import (
    Handler as CompleteProcedureHandler,
)
from cora.operation.features.end_iteration.command import EndProcedureIteration
from cora.operation.features.end_iteration.handler import Handler as EndProcedureIterationHandler
from cora.operation.features.hold_procedure.command import HoldProcedure
from cora.operation.features.hold_procedure.handler import Handler as HoldProcedureHandler
from cora.operation.features.resume_procedure.command import ResumeProcedure
from cora.operation.features.resume_procedure.handler import Handler as ResumeProcedureHandler
from cora.operation.features.start_iteration.command import StartProcedureIteration
from cora.operation.features.start_iteration.handler import (
    Handler as StartProcedureIterationHandler,
)
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.features.start_procedure.handler import Handler as StartProcedureHandler
from cora.operation.ports.compute_port import (
    ArtifactNotFoundError,
    ArtifactRef,
    ComputeJobFailedError,
    ComputeNotAvailableError,
    ComputePort,
    ComputeSubmitRejectedError,
    ComputeTimeoutError,
    JobSpec,
    MeasurementNotFoundError,
)
from cora.operation.ports.control_port import (
    ActuationKind,
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlPort,
    ControlTimeoutError,
    ControlValueCoercionError,
    ControlWriteRejectedError,
    Measurement,
    NoAdapterForAddressError,
)
from cora.operation.ports.decide_port import (
    DecideAccessDeniedError,
    DecideAdviceMalformedError,
    DecideEvidenceRejectedError,
    DecideNotAvailableError,
    DecidePort,
    DecideTimeoutError,
    SteeringAdvice,
    SteeringBudget,
    SteeringEvidence,
    SteeringObjective,
    SteeringObservation,
    SteeringPoint,
    SteeringSpace,
    SteeringVerdict,
    advice_to_audit_fields,
)
from cora.recipe.aggregates.recipe.body import CaptureRef, OutputRef
from cora.shared.text_bounds import REASON_MAX_LENGTH

_CONTROL_ERRORS: tuple[type[Exception], ...] = (
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlWriteRejectedError,
    ControlValueCoercionError,
    ControlAccessDeniedError,
    NoAdapterForAddressError,
)
"""The closed set of `Control*Error` classes the Conductor maps to
`ConductorFailure`. Tuple shape lets the `except` clause stay
declarative; new exception classes in `cora.operation.ports.control_port`
must be added here explicitly (no `Exception` catch-all so non-port
exceptions still propagate to the caller's task).

`NoAdapterForAddressError` is included so a misconfigured
`ControlPortRegistry` (an address with no matching prefix) records
a structured step-failure rather than letting an opaque exception
propagate to the route layer and strand the Procedure in `Running`."""


_LIFECYCLE_RERAISE: tuple[type[Exception], ...] = (
    UnauthorizedError,
    ProcedureNotFoundError,
    ConcurrencyError,
)
"""Exceptions from the lifecycle handlers (start / complete /
abort) that `conduct()` re-raises rather than recording as a
ConductorFailure. These already have HTTP exception mappers
registered on the BC's FastAPI routes (403 / 404 / 409) so
re-raising lets the route layer return the right status code +
preserves authz-deny + not-found telemetry. Anything else from
the lifecycle handlers (Procedure*CannotStart/Complete/Abort,
ProcedureAssetDecommissioned, supply-gate errors) is a legitimate
"this Procedure cannot transition right now" outcome that lands
in the result body as a structured lifecycle failure."""


_STEP_KIND_SETPOINT = "setpoint"
_STEP_KIND_ACTION = "action"
_STEP_KIND_CHECK = "check"
_STEP_KIND_CAPTURE = "capture"
_STEP_KIND_COMPUTE = "compute"

_COMPUTE_ERRORS: tuple[type[Exception], ...] = (
    ComputeSubmitRejectedError,
    ComputeNotAvailableError,
    ComputeTimeoutError,
    ComputeJobFailedError,
    MeasurementNotFoundError,
    ArtifactNotFoundError,
)
"""The closed set of `Compute*Error` classes a ComputeStep maps to a
recorded step failure + `ConductorFailure`. Mirrors `_CONTROL_ERRORS`:
new ComputePort exception classes must be added here explicitly (no
`Exception` catch-all so non-port exceptions still propagate to the
caller's task). `MeasurementNotFoundError` is the value arm's
artifact-missing analogue; `ArtifactNotFoundError` the file arm's. A
non-`Succeeded` terminal (Failed / Cancelled / TimedOut returned
without an exception) is the further halt path, handled inline in
`_run_compute`."""

_ERROR_UNRESOLVED_CAPTURE = "UnresolvedCaptureRef"
"""error_class for a SetpointStep CaptureRef whose name was never captured
in this conduct (e.g. resumed past the capturing step). Loud-fail label,
not an exception type: the failure is recorded + returned, not raised."""

_ERROR_DUPLICATE_CAPTURE = "DuplicateCapture"
"""error_class for a CaptureStep re-capturing an already-filled name within
one conduct (an authoring error the recipe validation also rejects). Also
used by a ComputeStep deposit (slice 6c) into an already-filled slot."""

_ERROR_UNRESOLVED_OUTPUT = "UnresolvedOutputRef"
"""error_class for a ComputeStep `OutputRef` input whose `output_name` was never
deposited in this conduct (e.g. resumed past the producing step, or an authoring
mismatch). The compute-branch twin of `_ERROR_UNRESOLVED_CAPTURE`. Loud-fail
label, not an exception type: the failure is recorded + returned BEFORE any
in-flight marker or submit, naming the unresolved element index + name + the
deposited names so the mismatch is diagnosable from the journal."""

_ERROR_DUPLICATE_OUTPUT = "DuplicateOutput"
"""error_class for a ComputeStep `output_ref_name` deposit into an already-filled
`outputs` slot within one conduct. The compute-branch twin of
`_ERROR_DUPLICATE_CAPTURE` (no `Ref` suffix, like `DuplicateCapture`). Two
file-arm steps depositing the same output name is an authoring error the recipe
validation also rejects (`DuplicateRecipeOutputError`)."""

_ERROR_MEASUREMENT_NOT_FOUND = "ComputeMeasurementNotFound"
"""error_class for a ComputeStep `capture_name` deposit (slice 6c) when no
produced Measurement carries that name. Loud-fail label, not an exception
type; the failure is recorded + returned, naming the wanted name + the
available names so an authoring mismatch is diagnosable from the journal."""

_ERROR_AMBIGUOUS_MEASUREMENT = "ComputeMeasurementAmbiguous"
"""error_class for a ComputeStep `capture_name` deposit (slice 6c) when more
than one produced Measurement carries the name. No first-wins: an ambiguous
deposit is an authoring error (the solver emitted a duplicate-named value)."""

_ERROR_ITERATION_CAP_REACHED = "ConvergenceIterationCapReached"
"""error_class on the lifecycle `ConductorFailure` that `conduct_until_converged`
returns when the patience cap trips before the criterion is met (slice 6c).
Loud-fail label, not an exception type: the loop aborts the Procedure (a
planned terminal) and surfaces this so the caller can distinguish a
never-converged routine from a step fault."""

_ABSOLUTE_MAX_ITERATIONS = 10_000
"""Absolute ceiling on convergence-loop passes, applied EVEN WHEN the patience
cap (`max_consecutive_unconverged_iterations`) is None. Defense-in-depth: every
pass actuates hardware (a ComputeStep submit + SetpointStep writes), so an
uncapped loop with a never-matching criterion would actuate without bound. The
ceiling is generous (a real alignment converges in single-digit passes); it is
a runaway backstop, not a tuning knob."""

_ERROR_ABSOLUTE_ITERATION_CEILING = "AbsoluteIterationCeilingReached"
"""error_class on the lifecycle `ConductorFailure` that `conduct_until_converged`
returns when the absolute iteration ceiling (`_ABSOLUTE_MAX_ITERATIONS`) trips.
Distinct from `ConvergenceIterationCapReached` (the operator-set patience cap):
this is the unconditional runaway backstop that bites even when no patience cap
was supplied."""

_DECIDE_ERRORS: tuple[type[Exception], ...] = (
    DecideNotAvailableError,
    DecideTimeoutError,
    DecideEvidenceRejectedError,
    DecideAdviceMalformedError,
    DecideAccessDeniedError,
)
"""The closed set of `Decide*Error` classes `conduct_until_advised` folds into a
recorded steering decision rather than crashing the loop. Mirrors `_CONTROL_ERRORS`
/ `_COMPUTE_ERRORS`: a brain that is unreachable, slow, refuses the evidence,
returns malformed advice, or denies the principal lands a closed iteration plus a
best-effort abort carrying the brain's `error_class`, exactly as the port docstring
promises (the caller folds a raised exception into a recorded decision). New
DecidePort exception classes must be added here explicitly (no `Exception`
catch-all so non-port exceptions still propagate to the caller's task)."""

_SOURCE_KIND_DECIDE = "decide"
"""Conductor-local pseudo-`source_kind` used on the `ConductorFailure` that
`conduct_until_advised` returns when the brain raised a `Decide*Error`. Like
`_SOURCE_KIND_LIFECYCLE` it is NOT a step kind (no step entry is recorded for a
brain consult); it labels the failure origin as the decide seam, not a walked
step, so a caller distinguishes a brain fault from a hardware step fault."""

_CAPTURE_REF_KEY = "__capture__"
"""Wire-format sentinel key for a `CaptureRef` value in the pinned conduct
step payload (mirrors the Recipe BC's `__capture__` form). A `SetpointStep`
whose value is a `CaptureRef` serializes to `{"__capture__": name}` so it
rides `ResolvedStepsRecorded` + the determinism hash as an opaque sentinel
and round-trips at resume; the Conductor resolves it at execute time."""

_OUTPUT_REF_KEY = "__output__"
"""Wire-format sentinel key for an `OutputRef` element of a ComputeStep's
`input_uris` in the pinned conduct step payload (mirrors the Recipe BC's
`__output__` form). A ComputeStep input element that is an `OutputRef`
serializes to `{"__output__": name}` so it rides `ResolvedStepsRecorded` + the
determinism hash as an opaque sentinel and round-trips at resume; the Conductor
resolves it to a produced artifact's URI at execute time. The element-wise
encoding is load-bearing for the hash: `canonical_json_bytes` has no `default=`,
so a raw `OutputRef` in the whole-list form would crash the encoder."""


def _input_uri_to_wire(uri: "str | OutputRef") -> Any:
    """Serialize ONE ComputeStep `input_uris` element (URI or `OutputRef`) to wire form.

    Shared across every conductor serializer so a raw `OutputRef` never reaches
    the JSON / hash encoder. An `OutputRef` becomes `{"__output__": name}`; a
    literal URI passes through. Mirrors the Recipe BC's `_input_uri_to_wire`."""
    if isinstance(uri, OutputRef):
        return {_OUTPUT_REF_KEY: uri.output_name}
    return uri


def _input_uri_from_wire(value: Any) -> "str | OutputRef":
    """Deserialize ONE wire ComputeStep `input_uris` element; reconstruct an `OutputRef`.

    Inverse of `_input_uri_to_wire`: a `{"__output__": name}` dict becomes an
    `OutputRef`, any other value (a literal URI string) passes through."""
    if isinstance(value, dict) and set(cast("dict[str, Any]", value)) == {_OUTPUT_REF_KEY}:
        return OutputRef(output_name=str(cast("dict[str, Any]", value)[_OUTPUT_REF_KEY]))
    return cast("str", value)


"""Closed-set step-kind discriminators from [[project_operation_design]].
The source of truth for the value set is `STEP_KIND_VALUES` on the
Procedure aggregate (re-imported above); the architecture fitness
`test_conductor_step_kinds_match_procedure` pins that the `_STEP_KIND_*`
constants + `Step` union arms here stay in sync with that set, so the
count is derived, never hard-coded.

`_SOURCE_KIND_LIFECYCLE` below is a Conductor-local pseudo-kind used
only on `ConductorFailure` (lifecycle failures do not record a step
entry), so it is intentionally NOT a member of `STEP_KIND_VALUES`."""

_SOURCE_KIND_LIFECYCLE = "lifecycle"
"""Pseudo-`source_kind` used on `ConductorFailure` when the failure
came from the surrounding lifecycle handlers (start_procedure /
complete_procedure / abort_procedure) rather than a step in the
caller-supplied sequence. Lifecycle failures do not record a
Activity entry; the failure surfaces only on the result."""

_LIFECYCLE_TARGET_START = "start"
_LIFECYCLE_TARGET_COMPLETE = "complete"
_LIFECYCLE_TARGET_ABORT = "abort"

_RESULT_OK = "ok"
_RESULT_FAILED = "failed"
"""Conductor-local convention inside the step payload body; today's
projections do not split on it, but the field is pinned so future
read-side filters can separate successful vs failed steps without
parsing the message string."""

_RESULT_IN_FLIGHT = "in_flight"
"""Pre-effect in-flight marker discriminator, written to a SEPARATE
step entry BEFORE a side-effecting step (setpoint / action) actuates,
then followed by the `ok` / `failed` outcome entry after. A check is a
pure read (always safe to re-run), so it records NO marker -- only its
single outcome entry.

The marker is what lets a future resume identify the one step that was
mid-flight when a conduct halted: an `in_flight` entry with no matching
outcome entry for the same `step_index` is the interrupted step. The
marker is recorded even when the effect then raises or is cancelled
(the marker append completes before the effect runs); that is the
point -- a crashed write leaves a marker-without-outcome behind so the
step is recoverable. See [[project_resumable_conduct_design]] Tier 1."""

_QUALITY_GOOD = "Good"

_RESUME_HALT_ERROR_CLASS = "AcquisitionResumeRequiresOperator"
"""`error_class` on the `ConductorFailure` that `execute_from` returns when
a resume reaches an `ActionStep` (an acquisition). It is NOT an exception
and NOT a step failure: re-running an interrupted acquisition is
non-idempotent (fly-scan triggers are one-shot, a mid-arm collect reads
identically for finished / aborted / never-armed), so resume HALTS and
hands the decision (redo-fresh vs reseed) back to the operator rather than
auto-skipping or auto-rerunning. See [[project_resumable_conduct_design]]."""


class ResumePolicy(StrEnum):
    """How `execute_from` re-establishes state while replaying a step-list tail.

    `RE_ESTABLISH` (the only member today): re-drive setpoints (absolute
    writes are idempotent; CORA has no relative-setpoint type), re-run
    checks as fresh gates, and HALT on an acquisition (`ActionStep`) for an
    operator decision. This is the locked default per
    [[project_resumable_conduct_design]].

    A future `COMPARE` member (read-and-compare instead of re-drive) is an
    Anti-hook-until-lease: its single-writer guarantee is unsatisfiable on a
    multi-writer floor until a Conduit/Surface write-ownership lease exists,
    so it is deliberately absent rather than stubbed.
    """

    RE_ESTABLISH = "re_establish"


@dataclass(frozen=True)
class SetpointStep:
    """One setpoint operation: write `value` to `address`.

    `address` is a substrate-agnostic string per
    [[project_control_port_design]]. The routed `ControlPort` adapter
    parses substrate-specific syntax (EPICS PV name, Tango TRL, OPC
    UA NodeId) so the Conductor never branches on substrate.

    `verify` (opt-in) requests an immediate post-write `ControlPort.read`
    so the actual landed value joins the recorded payload as evidence.
    The post-read is OBSERVATIONAL only: a `Control*Error` from the
    read OR a non-Good quality on the reading does NOT halt the
    Conductor. The write already succeeded; the evidence is incomplete
    but not failed. Operators who need HALT-on-mismatch use a
    `CheckStep` right after the setpoint instead.

    `value` may be a `CaptureRef`, which the Conductor resolves at execute
    time against the per-conduct `captures` dict (filled by an earlier
    `CaptureStep`) before writing. The ref rides through recipe expansion
    and the determinism hash as an opaque sentinel; only execution
    resolves it. A `CaptureRef` whose name was never captured halts the
    step with a recorded failure.
    """

    address: str
    value: int | float | bool | str | tuple[Any, ...] | CaptureRef
    verify: bool = False


@dataclass(frozen=True)
class ActionStep:
    """One action invocation: look up `name` in the registry, run with `params`.

    Action bodies are deployment-supplied callables that compose
    `ControlPort` calls (and / or external side effects) into named
    operations. The Conductor treats the body as opaque: it knows
    the name + params + the registry, and records whatever the body
    returns as evidence in the step payload.

    `params` is a JSON-shaped Mapping; tests can pass plain `dict`,
    runtime callers should pass an immutable `MappingProxyType` if
    they need to share params across steps without copy.
    """

    name: str
    params: Mapping[str, Any] = field(default_factory=dict[str, Any])


@dataclass(frozen=True)
class EqualsCriterion:
    """Criterion: the observed value must equal `expected` exactly.

    Equality is Python `==`: numeric comparison for numbers (mind
    float exactness for non-integer values), structural equality for
    tuples + strings. For floats with tolerance use
    `WithinToleranceCriterion` instead.
    """

    expected: int | float | bool | str | tuple[Any, ...]


@dataclass(frozen=True)
class WithinToleranceCriterion:
    """Criterion: numeric reading must satisfy |value - expected| <= tolerance.

    `tolerance` is the absolute allowed deviation; non-negative.
    Non-numeric values (the read returned a string, tuple, etc.) are
    treated as a clean mismatch rather than a coercion exception:
    operators see "criterion mismatch" rather than a substrate-shaped
    error, which is the right read of "this reading isn't checkable
    by this criterion."
    """

    expected: float
    tolerance: float


CheckCriterion = EqualsCriterion | WithinToleranceCriterion
"""Closed discriminator for `CheckStep` acceptance.

Open to additive variants: `OneOf` (allowed value set), `Matches`
(regex on string), `Within` (range with separate min/max). New
variants land as code edits plus matching `_criterion_to_dict` +
`_criterion_matches` arms; the payload `kind` field keeps wire shape
stable."""


@dataclass(frozen=True)
class CheckStep:
    """One post-condition verification: read `address`, evaluate `criterion`.

    The Conductor reads the address via `ControlPort.read`, requires
    `Measurement.quality == "Good"`, then evaluates `criterion` against
    `Measurement.value`. Any of (read raised `Control*Error`, quality
    not Good, criterion did not match) halts execution with a
    recorded failure entry. The recorded payload carries the
    observed reading so post-hoc inspection has the evidence.
    """

    address: str
    criterion: CheckCriterion


@dataclass(frozen=True)
class CaptureStep:
    """Read `address` at execute time and store the value into `capture_name`.

    A capture is fundamentally a READ (it reuses the same `ControlPort.read`
    path as a `CheckStep`), distinct from a `SetpointStep` (which commands)
    and a `CheckStep` (which reads and gates). It OBSERVES where the axis
    actually is and records that value in the Conductor's per-conduct
    `captures` dict, so a later `SetpointStep` with a `CaptureRef` can
    return to it. The captured value is the readback (the truth on the
    wire), not the commanded value.

    The read must yield a finite number (`captures` exist for arithmetic-
    free restore, but the finite guard catches a non-numeric / NaN read
    before it poisons a later setpoint); a non-finite or non-numeric read,
    a `Control*Error`, or a re-capture into an already-filled name halts
    the step with a recorded failure.
    """

    address: str
    capture_name: str


@dataclass(frozen=True)
class ComputeStep:
    """One compute job: submit `command` over `ComputePort`, surface its output.

    The compute sibling of `ActionStep`. Where an action runs a deployment
    body composing ControlPort calls, a ComputeStep submits a job to a
    compute substrate (`ComputePort.submit`), awaits its terminal state, and
    surfaces what the job produced. It drives ONE of the port's two output
    arms by the presence of `output_uri`:

    - VALUE arm (`output_uri is None`): fetch the structured value the job
      produced (`fetch_measurements`) and record each `Measurement` on the
      activity log. An align-resolution routine measures the detector pixel
      size from two already-acquired frames and yields one scalar
      `Measurement` that homes to a Calibration.
    - FILE arm (`output_uri is not None`): fetch a reference to the file the
      job wrote (`fetch_artifact_ref`) and surface the `ArtifactRef` on the
      conduct's result so a Dataset can be registered against it. A
      reconstruction writes a volume to `output_uri`.

    Fields mirror the output-bearing subset of `JobSpec`: `command` is the
    argv the substrate launches; `output_uri` selects the file arm (and names
    where the job writes); `parameters` carries the validated parameter set.
    `resources` / `working_dir` / `env` are substrate-decides defaults. A
    ComputeStep is side-effecting (a job submission is non-idempotent at the
    substrate), so it records a pre-effect in-flight marker like a setpoint /
    action.

    `input_uris` elements are each a literal URI (a well-known path an
    acquisition action body wrote) OR an `OutputRef` naming an EARLIER file-arm
    step's produced artifact. An `OutputRef` element rides through expansion +
    the determinism hash as an opaque sentinel; the Conductor resolves it at
    execute time (BEFORE building the JobSpec) to the produced artifact's URI
    out of the per-conduct `outputs` bus, so the JobSpec + ComputePort never see
    a ref. A tuple of independently-named `OutputRef`s IS the fan-in (a step
    consuming several upstream outputs). An `OutputRef` whose name was never
    deposited loud-fails (`UnresolvedOutputRef`) with NO in-flight marker and
    nothing submitted, parity with a `SetpointStep` `CaptureRef`.

    `output_ref_name` names the `outputs` slot the produced `ArtifactRef`
    deposits into (the FILE arm), the artifact-bus chaining twin of
    `capture_name`. When set, after the file arm fetches the `ArtifactRef` and
    records its OK outcome the Conductor writes the full `ArtifactRef` into the
    per-conduct `outputs` dict so a later step's `OutputRef` input resolves to
    its URI; loud-fails (`DuplicateOutput`) on an already-filled slot. None (the
    default): the artifact is surfaced but no slot is filled.

    `capture_name` names the captures slot the produced scalar deposits into
    (the VALUE arm), the chaining sibling of `CaptureStep.capture_name`. When
    set, after the job succeeds the Conductor selects the named `Measurement`
    (loud-failing on absent / ambiguous / non-Good / non-finite), then writes
    its value into the per-conduct `captures` dict so a later `SetpointStep`
    `CaptureRef` (intra-pass correction) or the convergence-loop predicate
    (`conduct_until_converged`) can read it. None (the default): measurements
    are recorded + surfaced but no slot is filled. A compute-deposited slot
    (capture or output) lives only within one forward `execute()`, never across
    a resume (both buses start empty on replay).
    """

    command: tuple[str, ...]
    input_uris: tuple[str | OutputRef, ...] = ()
    output_uri: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict[str, Any])
    capture_name: str | None = None
    output_ref_name: str | None = None


Step = SetpointStep | ActionStep | CheckStep | CaptureStep | ComputeStep
"""The closed discriminated union of step kinds the Conductor walks.

Mirrors the open `StepKind` Literal in the Procedure aggregate; the
Conductor enforces tighter typing via this union so a malformed step is a
type error, not a runtime branch. The arm count is pinned against
`STEP_KIND_VALUES` by `test_conductor_step_kinds_match_procedure`."""


def _steering_probe_point(space: SteeringSpace) -> SteeringPoint:
    """The space's authored-default coordinate (lower bound, or first choice).

    Used in two places that must agree: the `conduct_until_advised` wire-time
    disjointness guard probes `point_to_captures` with it, and the steered loop
    seeds the FIRST pass with it. Pass 1 has no brain advice yet, so it measures
    at this authored default position; the brain's `next_point` seeds every
    later pass. A continuous axis defaults to its `lower` bound, a discrete /
    categorical axis to its first `choice`, and an unbounded axis to `0.0`."""
    return SteeringPoint(
        coordinates={
            axis.name: (
                axis.lower if axis.lower is not None else (axis.choices[0] if axis.choices else 0.0)
            )
            for axis in space.axes
        }
    )


def _validate_advice_point(point: SteeringPoint | None, space: SteeringSpace) -> None:
    """Raise `DecideAdviceMalformedError` unless a Measure advice's `next_point`
    covers exactly the space axis names.

    `SteeringAdvice.__post_init__` checks the verdict / next_point pairing but
    cannot see the space, so a brain may return a structurally-valid Measure
    whose `next_point` omits, misnames, or over-fills an axis. Seeding such a
    point would `KeyError` in `point_to_captures` (a missing axis) or clobber a
    non-axis captures slot (an extra key). The loop calls this right after
    `advise_next`, inside the Decide-error try, so a malformed point is FOLDED
    into a recorded steering decision rather than crashing the loop, symmetric
    with a raised `Decide*Error`."""
    axis_names: set[str] = {axis.name for axis in space.axes}
    keys: set[str] = set(point.coordinates) if point is not None else set()
    if keys != axis_names:
        raise DecideAdviceMalformedError(
            f"advised point keys {sorted(keys)!r} must cover exactly the steering "
            f"axis names {sorted(axis_names)!r}"
        )


def _require_finite_number(value: Any, address: str) -> float:
    """Return `value` as a finite number or raise a Conductor-recordable failure.

    A captured axis read feeds a later restore setpoint, so it must be a
    finite number. `Measurement.value` is typed `Any`; a non-numeric read (a
    categorical / mis-addressed leaf) or a non-finite float (NaN / +-inf,
    e.g. an EPICS UDF) would otherwise propagate silently. Mapping it to
    `ControlValueCoercionError` (a member of `_CONTROL_ERRORS`) lets the
    Conductor record a structured step failure instead of letting a bare
    `TypeError` escape or a NaN poison a downstream setpoint.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ControlValueCoercionError(address, type(value).__name__, "number")
    if not math.isfinite(value):
        raise ControlValueCoercionError(address, repr(value), "finite number")
    return value


@dataclass(frozen=True)
class ActionContext:
    """Dependencies + per-call inputs the Conductor passes to action bodies.

    Bundled so additive fields (correlation_id, procedure_id, a
    cancel-token, a structured logger) can land without churning
    every action body's signature. Bodies destructure what they need
    and ignore the rest.
    """

    control_port: ControlPort
    clock: Clock
    params: Mapping[str, Any]


ActionBody = Callable[[ActionContext], Awaitable[Mapping[str, Any]]]
"""Callable an `ActionRegistry` maps action names onto.

Returns a JSON-shaped `Mapping` recorded as `result_data` in the
step payload. Raising any `Control*Error` halts the Conductor and
records the failure; raising anything else propagates uncaught.
Bodies that want a domain-level "soft fail" return a result Mapping
carrying their own status field."""


class ActionRegistry(Protocol):
    """Read-only lookup from action name to `ActionBody`.

    A Protocol (not a concrete dict-backed class) so deployments can
    back the registry with whatever discovery mechanism fits: hand-
    built dict in tests, config-file loader in 2-BM, entry-point
    scan in a future plugin world. `InMemoryActionRegistry` (below)
    is the dict-backed default the Conductor's unit tests use.
    """

    def lookup(self, name: str) -> ActionBody | None: ...


@dataclass(frozen=True)
class InMemoryActionRegistry:
    """Dict-backed `ActionRegistry`; the default for tests + small deployments.

    Construct from a mapping at app wire-up time; the dict shape is
    intentional (not a callable Protocol) so missing-name lookups
    return None rather than raising, keeping the failure-recording
    path uniform with `Control*Error` paths.
    """

    bodies: Mapping[str, ActionBody]

    def lookup(self, name: str) -> ActionBody | None:
        return self.bodies.get(name)


@dataclass(frozen=True)
class ConductorFailure:
    """First halt-condition the Conductor hit during a run.

    Covers per-step failures (a Control*Error during setpoint write
    or check read, an UnknownActionError, a CheckFailedError) AND
    lifecycle failures from `conduct()` (start_procedure rejected,
    complete_procedure rejected).

    `step_index` is the position in the caller-supplied step list
    when the failure was inside a step; `None` when the failure was
    a lifecycle handler call (start / complete / abort) and no step
    was involved. `source_kind` is "setpoint" / "action" / "check" for
    per-step failures, "lifecycle" for FSM-handler failures.
    `target` is the address (setpoint/check) or name (action) or
    lifecycle phase ("start" / "complete" / "abort").

    `error_class` is the simple class name (no module prefix); the
    `message` carries the formatted `str(exc)` output. Both land in
    the recorded step payload (per-step failures) so log inspection
    from the read-side matches what's on the `ConductorResult`.
    """

    step_index: int | None
    source_kind: str
    target: str
    error_class: str
    message: str


@dataclass(frozen=True)
class ConductorResult:
    """Outcome of a `Conductor.execute` call.

    `completed_count` is the number of steps that fully ran AND
    recorded a success entry. The failing step (if any) is NOT
    counted in `completed_count`; its failure IS recorded in the
    logbook AND surfaced in `failure`.

    `actuation_kind` is the provenance fact the producing Dataset
    snapshots: `Physical` / `Simulated` / `Hybrid` when the conduct
    touched a routing table that declares simulated routes, else
    `None` (no routing table to consult, e.g. an opt-out in-memory
    deployment) which leaves the promotion gate inactive. It reflects
    routes ATTEMPTED, not only successfully actuated: a dispatch that
    resolves a simulated route and then raises still taints the conduct
    (any simulator touch is disqualifying), so the failure-path result
    still reports the kind. Do not "fix" the observe-before-dispatch
    ordering in `_ActuationObserver` without revisiting this contract.

    `held` is True ONLY when `try_conduct` paused the Procedure to `Held`
    on a recoverable step failure (and the hold transition itself
    succeeded). Every other path (`execute` / `conduct` / `execute_from`
    / `reconduct`, and a `try_conduct` whose hold itself failed) leaves it
    False. It reflects the ACTUAL transition, not the mere recoverability
    of the failure, so a caller can distinguish a resumable `Held` outcome
    from a terminal `Aborted` one (both carry `succeeded=False` + `failure`).

    `measurements` accumulates the `Measurement`s every value-arm
    `ComputeStep` produced; `artifacts` accumulates the `ArtifactRef`s
    every file-arm `ComputeStep` produced. `execute()` collects each in
    order (mirroring `completed_count`) on BOTH the success and the
    failure construction, so a caller reads the produced outputs without
    re-parsing the activity log even when a later step halts. Both empty
    on a conduct with no ComputeStep. The `conduct` / `reconduct`
    `replace()` paths preserve them.

    `outputs` is the per-conduct artifact bus keyed by `output_ref_name`: a
    file-arm `ComputeStep` with an `output_ref_name` deposits its full
    `ArtifactRef` under that name, so a caller selects the Dataset-of-record by
    NAME (e.g. `outputs["recon"]`) rather than by document position
    (`artifacts[-1]` would pick a stray post-terminal QC step). Empty for a
    conduct with no depositing file-arm step. Surfaced alongside the flat
    `artifacts` tuple (which keeps every file-arm artifact in order, named or
    not).
    """

    procedure_id: UUID
    completed_count: int
    failure: ConductorFailure | None = None
    actuation_kind: ActuationKind | None = None
    held: bool = False
    measurements: tuple[Measurement, ...] = ()
    artifacts: tuple[ArtifactRef, ...] = ()
    outputs: Mapping[str, ArtifactRef] = field(default_factory=dict[str, ArtifactRef])

    @property
    def succeeded(self) -> bool:
        return self.failure is None


class _ActuationObserver:
    """Per-conduct `ControlPort` decorator that records actuation provenance.

    Wraps the Conductor's `ControlPort` for the duration of one
    `execute` call so every dispatch (setpoint write, verify/check
    read, and action-body IO) passes through one seam. For each touched
    address it asks the inner port whether the address routes to a
    simulated adapter, then collapses the observations to an
    `ActuationKind`.

    When the inner port does not expose `route_is_simulated` (a bare
    adapter or an opt-out in-memory deployment with no routing table),
    nothing is recorded and `actuation_kind` stays `None`, leaving the
    promotion gate inactive. The simulated determination is the
    inner port's declared per-route flag, never inferred here from the
    adapter class: a soft IOC speaks real Channel Access yet is a
    simulator.
    """

    def __init__(self, inner: ControlPort) -> None:
        self._inner = inner
        self._route_is_simulated: Callable[[str], bool] | None = getattr(
            inner, "route_is_simulated", None
        )
        self._simulated_flags: set[bool] = set()

    def _observe(self, address: str) -> None:
        if self._route_is_simulated is None:
            return
        # A routing miss surfaces on the real read/write below; here it
        # just means there is nothing to observe for this address.
        with contextlib.suppress(NoAdapterForAddressError):
            self._simulated_flags.add(bool(self._route_is_simulated(address)))

    async def read(self, address: str) -> Measurement:
        self._observe(address)
        return await self._inner.read(address)

    async def write(
        self,
        address: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        self._observe(address)
        await self._inner.write(address, value, wait=wait, timeout_s=timeout_s)

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:
        self._observe(address)
        return self._inner.subscribe(address)

    @property
    def actuation_kind(self) -> ActuationKind | None:
        if not self._simulated_flags:
            return None
        if self._simulated_flags == {True}:
            return ActuationKind.SIMULATED
        if self._simulated_flags == {False}:
            return ActuationKind.PHYSICAL
        return ActuationKind.HYBRID


class Conductor:
    """Operation BC Layer-2 runtime: walks `Step`s via ControlPort + action registry.

    Stateless walker. Construct once at app wire-up time; call
    `execute` per Procedure execution. Per-call state lives on the
    returned `ConductorResult`.

    The Conductor calls the `append_activities` handler (not the
    underlying `ActivityStore`) so lazy-open + status guard + authorization
    stay inside that slice. See module docstring for failure mode +
    out-of-scope.
    """

    def __init__(
        self,
        *,
        control_port: ControlPort,
        append_step: AppendProcedureActivitiesHandler,
        clock: Clock,
        id_generator: IdGenerator,
        action_registry: ActionRegistry | None = None,
        compute_port: ComputePort | None = None,
        start_procedure: StartProcedureHandler | None = None,
        complete_procedure: CompleteProcedureHandler | None = None,
        abort_procedure: AbortProcedureHandler | None = None,
        resume_procedure: ResumeProcedureHandler | None = None,
        hold_procedure: HoldProcedureHandler | None = None,
        start_iteration: StartProcedureIterationHandler | None = None,
        end_iteration: EndProcedureIterationHandler | None = None,
    ) -> None:
        self._control_port = control_port
        self._append_step = append_step
        self._clock = clock
        self._id_generator = id_generator
        self._action_registry: ActionRegistry = action_registry or InMemoryActionRegistry({})
        # BORROWED reference: the composition root owns the single ComputePort
        # instance (shared with the Reckoner) and owns its `aclose`. The
        # Conductor never closes it. None when no compute substrate is wired;
        # dispatching a ComputeStep then raises RuntimeError (a wiring bug).
        self._compute_port = compute_port
        self._start_procedure = start_procedure
        self._complete_procedure = complete_procedure
        self._abort_procedure = abort_procedure
        self._resume_procedure = resume_procedure
        self._hold_procedure = hold_procedure
        self._start_iteration = start_iteration
        self._end_iteration = end_iteration

    async def execute(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        captures: dict[str, Any] | None = None,
    ) -> ConductorResult:
        """Walk `steps` in order; dispatch per kind + record outcome.

        Halts on the first `Control*Error`, `UnknownActionError`, or
        `CheckFailedError` (criterion mismatch or non-Good quality).
        The failing step is recorded in the logbook (`result="failed"`)
        BEFORE this returns; subsequent steps are NOT attempted. The
        Procedure's FSM is unchanged.

        Non-port, non-UnknownAction exceptions (programmer errors,
        KeyboardInterrupt, CancelledError) are NOT caught: they
        propagate to the caller so signals + cancellation behave
        normally and bugs surface.

        `captures` is the per-conduct runtime-value bus a `CaptureStep` /
        deposit-`ComputeStep` fills and a `CaptureRef` setpoint reads. None
        (the default) creates a FRESH dict, preserving the single-pass
        behavior. `conduct_until_converged` passes a fresh dict PER PASS and
        reads the convergence value out of it after the pass (the dict is
        mutated in place, so the caller's reference sees every deposit).

        The artifact bus (`outputs`, keyed by `output_ref_name`) is an internal
        LOCAL, never a kwarg: a file-arm `ComputeStep` deposits its `ArtifactRef`
        and a later step's `OutputRef` input reads it, both within this one
        walk. It is surfaced on the returned `ConductorResult.outputs` so a
        caller can select the Dataset-of-record by name.
        """
        envelope = _Envelope(
            procedure_id=procedure_id,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )
        observer = _ActuationObserver(self._control_port)
        if captures is None:
            captures = {}
        # The per-conduct artifact bus, keyed by `output_ref_name`. A LOCAL (not
        # a kwarg, per the slice-design S3 lock): producer + consumer are always
        # in one execute() walk, so it never escapes to the convergence-loop
        # caller (unlike `captures`, which the loop reads back per pass). A fresh
        # dict per execute() prevents cross-pass bleed.
        outputs: dict[str, ArtifactRef] = {}
        compute = _ComputeAccumulator()
        completed = 0
        for index, step in enumerate(steps):
            # Bind correlation_id to the ContextVar scoped per dispatch so
            # ControlPort adapters can emit `controlport.dispatch` events
            # without taking a kwarg. See `_control_dispatch_context` for
            # the why; contextvars survive each `await` inside `_dispatch`
            # and reset cleanly on exception.
            with with_dispatch_correlation_id(correlation_id):
                failure = await self._dispatch(
                    step,
                    index=index,
                    envelope=envelope,
                    port=observer,
                    captures=captures,
                    outputs=outputs,
                    compute=compute,
                )
            if failure is not None:
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=completed,
                    failure=failure,
                    actuation_kind=_fold_compute_kind(observer.actuation_kind, compute.kind),
                    measurements=tuple(compute.measurements),
                    artifacts=tuple(compute.artifacts),
                    outputs=dict(outputs),
                )
            completed += 1
        return ConductorResult(
            procedure_id=procedure_id,
            completed_count=completed,
            actuation_kind=_fold_compute_kind(observer.actuation_kind, compute.kind),
            measurements=tuple(compute.measurements),
            artifacts=tuple(compute.artifacts),
            outputs=dict(outputs),
        )

    async def execute_from(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        boundary: int,
        policy: ResumePolicy = ResumePolicy.RE_ESTABLISH,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        """Resume a halted conduct by REPLAYING the pinned resolved steps from `boundary`.

        `steps` is the FINAL resolved step list pinned on
        `ResolvedStepsRecorded` at first conduct (parse the event's
        `resolved_steps` back via `steps_from_payload`). Resume NEVER
        re-derives the step list -- a re-derived list could silently skip or
        mis-target a step (the end-of-run "home to 0" aliasing the
        start-of-run "home to 0" after an index shift). It replays
        `steps[boundary:]` verbatim:

          - `SetpointStep` -> RE-DRIVE (idempotent absolute write). The
            recorded `step_index` is the ABSOLUTE position in the step list, so the
            replayed journal lines up with the original conduct.
          - `CheckStep` -> RE-RUN as a fresh gate (a passing check proves
            "now", not "continuously", so it is re-evaluated).
          - `ActionStep` -> HALT for an operator decision (an interrupted
            acquisition is non-idempotent; see `_RESUME_HALT_ERROR_CLASS`).
            The action is NOT executed and NOTHING is recorded for it; the
            returned `ConductorResult.failure` carries the halt so the
            caller (a resume orchestrator) routes the decision.

        `boundary` is the re-establishment boundary from `ProcedureResumed`:
        the index from which re-drive + re-run resumes. `boundary >=
        len(steps)` replays an empty tail (a no-op resume). Like
        `execute`, this drives no FSM transition; it walks + records.

        See [[project_resumable_conduct_design]] Tier 1.
        """
        if boundary < 0:
            msg = f"boundary must be >= 0 (got {boundary})"
            raise ValueError(msg)
        if policy is not ResumePolicy.RE_ESTABLISH:  # pragma: no cover - only member today
            msg = f"unsupported resume policy: {policy}"
            raise ValueError(msg)
        envelope = _Envelope(
            procedure_id=procedure_id,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )
        observer = _ActuationObserver(self._control_port)
        # Captured slots start EMPTY on resume: a CaptureStep before the
        # boundary is not replayed, so a CaptureRef into it fails loud rather
        # than resolving against stale data. Persisting captures across a hold
        # (seed this dict from a ValueCaptured event) is the deferred resume leg.
        captures: dict[str, Any] = {}
        # The artifact bus is likewise empty on resume and never filled here: a
        # ComputeStep reached during replay halts for an operator decision (it is
        # never dispatched), so nothing deposits and no OutputRef resolves against
        # it. It is surfaced (always empty) on the success-path ConductorResult so
        # the resume contract stays symmetric with execute().
        outputs: dict[str, ArtifactRef] = {}
        completed = 0
        for index in range(boundary, len(steps)):
            step = steps[index]
            if isinstance(step, ActionStep):
                # Halt-for-operator: do not re-run an interrupted acquisition.
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=completed,
                    failure=ConductorFailure(
                        step_index=index,
                        source_kind=_STEP_KIND_ACTION,
                        target=step.name,
                        error_class=_RESUME_HALT_ERROR_CLASS,
                        message=(
                            f"resume halted at step {index} (action {step.name!r}): an "
                            "interrupted acquisition needs an operator decision "
                            "(redo-fresh vs reseed); not auto-rerun, not auto-skipped"
                        ),
                    ),
                    actuation_kind=observer.actuation_kind,
                )
            if isinstance(step, ComputeStep):
                # Halt-for-operator, same posture as an acquisition: a compute
                # submit is side-effecting / non-idempotent at the substrate
                # (re-submitting on resume could double-run a solver), so a
                # ComputeStep reached during replay hands the decision back
                # rather than auto-re-submitting. NOT executed, nothing recorded.
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=completed,
                    failure=ConductorFailure(
                        step_index=index,
                        source_kind=_STEP_KIND_COMPUTE,
                        target=" ".join(step.command),
                        error_class=_RESUME_HALT_ERROR_CLASS,
                        message=(
                            f"resume halted at step {index} (compute {step.command!r}): a "
                            "compute submit is non-idempotent and needs an operator decision "
                            "(redo-fresh vs reseed); not auto-rerun, not auto-skipped"
                        ),
                    ),
                    actuation_kind=observer.actuation_kind,
                )
            with with_dispatch_correlation_id(correlation_id):
                if isinstance(step, SetpointStep):
                    failure = await self._run_setpoint(
                        step, index=index, envelope=envelope, port=observer, captures=captures
                    )
                elif isinstance(step, CaptureStep):
                    failure = await self._run_capture(
                        step, index=index, envelope=envelope, port=observer, captures=captures
                    )
                else:
                    failure = await self._run_check(
                        step, index=index, envelope=envelope, port=observer
                    )
            if failure is not None:
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=completed,
                    failure=failure,
                    actuation_kind=observer.actuation_kind,
                )
            completed += 1
        return ConductorResult(
            procedure_id=procedure_id,
            completed_count=completed,
            actuation_kind=observer.actuation_kind,
            outputs=dict(outputs),
        )

    async def conduct(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        """Drive the full Procedure lifecycle: start -> execute -> complete | abort.

        Three-phase wrapper around `execute()`:

          1. Issue `start_procedure` (transitions Procedure Defined ->
             Running). If the start handler rejects (Procedure not
             in Defined, target Asset Decommissioned, Supply gate
             unmet, authz deny), return a lifecycle ConductorFailure
             without attempting any steps.
          2. Call `self.execute(steps)`. Step-level failures land in
             the result.failure as already documented.
          3. On execute success: issue `complete_procedure`
             (Running -> Completed). On execute failure: issue
             `abort_procedure` with a reason derived from the failed
             step. The abort is best-effort: if it ALSO fails, the
             original execute failure is what surfaces on the result
             (the Procedure stays Running and the operator must
             reconcile via state inspection).

        Requires `start_procedure` + `complete_procedure` +
        `abort_procedure` handlers to have been supplied at __init__.
        Raises `RuntimeError` if any of the three is missing; this
        is a wiring bug, not a runtime failure, so it propagates.

        Lifecycle failures (start rejected, complete rejected) carry
        `step_index=None`, `source_kind="lifecycle"`, `target` in
        `{"start", "complete", "abort"}`.
        """
        if (
            self._start_procedure is None
            or self._complete_procedure is None
            or self._abort_procedure is None
        ):
            raise RuntimeError(
                "Conductor.conduct() requires start_procedure + complete_procedure + "
                "abort_procedure handlers at __init__; only execute() is available "
                "without them."
            )
        envelope_kwargs: dict[str, Any] = {
            "principal_id": principal_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "surface_id": surface_id,
        }
        try:
            await self._start_procedure(
                StartProcedure(procedure_id=procedure_id), **envelope_kwargs
            )
        except _LIFECYCLE_RERAISE:
            raise
        except Exception as exc:
            return ConductorResult(
                procedure_id=procedure_id,
                completed_count=0,
                failure=ConductorFailure(
                    step_index=None,
                    source_kind=_SOURCE_KIND_LIFECYCLE,
                    target=_LIFECYCLE_TARGET_START,
                    error_class=type(exc).__name__,
                    message=str(exc),
                ),
            )
        # Bind the abort handler locally (the guard above proved it non-None)
        # for the cancel-orphan cleanup. If execute() is cancelled mid-flight
        # the Procedure is left non-terminal in `Running` with partial step
        # history; abort_orphan_on_cancel best-effort transitions it to Aborted
        # then re-raises so the caller's task still sees the cancellation. No
        # ConductorResult exists on cancellation, so the observed kind is
        # unrecoverable and the abort records None (a Dataset off a cancelled
        # conduct carries no proven kind).
        abort_procedure = self._abort_procedure
        async with abort_orphan_on_cancel(
            lambda: abort_procedure(
                AbortProcedure(procedure_id=procedure_id, reason="cancelled mid-execute"),
                **envelope_kwargs,
            )
        ):
            result = await self.execute(
                procedure_id=procedure_id,
                principal_id=principal_id,
                correlation_id=correlation_id,
                steps=steps,
                causation_id=causation_id,
                surface_id=surface_id,
            )
        if result.succeeded:
            try:
                await self._complete_procedure(
                    CompleteProcedure(
                        procedure_id=procedure_id,
                        # The bridge: the observed kind rides the terminal
                        # event the Conductor already issues, where the Data
                        # BC reads it back at Dataset registration. Raw
                        # ActuationKind value or None (no instrumented actuation).
                        actuation_kind=(
                            result.actuation_kind.value
                            if result.actuation_kind is not None
                            else None
                        ),
                    ),
                    **envelope_kwargs,
                )
            except _LIFECYCLE_RERAISE:
                raise
            except Exception as exc:
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=result.completed_count,
                    measurements=result.measurements,
                    artifacts=result.artifacts,
                    outputs=result.outputs,
                    failure=ConductorFailure(
                        step_index=None,
                        source_kind=_SOURCE_KIND_LIFECYCLE,
                        target=_LIFECYCLE_TARGET_COMPLETE,
                        error_class=type(exc).__name__,
                        message=str(exc),
                    ),
                )
            return result
        # execute failed; attempt abort with a derived reason. Best-effort:
        # if abort itself fails, surface the original step failure since
        # that is what the caller needs to triage.
        failure = result.failure
        assert failure is not None  # not result.succeeded implies failure
        reason = _derive_failure_reason(failure)
        with contextlib.suppress(Exception):
            await self._abort_procedure(
                AbortProcedure(
                    procedure_id=procedure_id,
                    reason=reason,
                    # Honest provenance for a Dataset off an aborted conduct:
                    # routes attempted before the failing step still taint it.
                    actuation_kind=(
                        result.actuation_kind.value if result.actuation_kind is not None else None
                    ),
                ),
                **envelope_kwargs,
            )
        return result

    async def try_conduct(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        """Drive the lifecycle like `conduct()`, but PAUSE to Held on a recoverable failure.

        The pause-capable twin of `conduct()`. Identical start -> execute ->
        complete-on-success path; the only divergence is the failure branch:

          - a RECOVERABLE step failure (setpoint / check: re-drivable /
            re-runnable on resume) -> best-effort `hold_procedure` (Running ->
            Held). On a successful hold the result carries `held=True` so the
            caller can offer `reconduct`; if the hold itself fails the
            Procedure is left Running (same posture as conduct's best-effort
            abort that fails) and `held` stays False.
          - a NON-recoverable step failure (an action: an interrupted
            acquisition is not auto-resumable, Tier 2) -> best-effort
            `abort_procedure`, exactly like `conduct()`. Holding here would
            strand a Procedure whose replay tail starts with an acquisition
            that `reconduct` can only halt-for-operator on.
          - lifecycle failures (start / complete rejected) and a mid-execute
            `CancelledError` keep `conduct()`'s behavior verbatim (no hold).

        Requires `start_procedure` + `complete_procedure` + `abort_procedure`
        + `hold_procedure` handlers at __init__; raises `RuntimeError` (a
        wiring bug) otherwise.

        This is the Tier-1 producer that makes a Held + pinned-resolved-steps
        state reachable, so the `reconduct` resume path has something to
        resume. See [[project_resumable_conduct_design]] Tier 1.
        """
        if (
            self._start_procedure is None
            or self._complete_procedure is None
            or self._abort_procedure is None
            or self._hold_procedure is None
        ):
            raise RuntimeError(
                "Conductor.try_conduct() requires start_procedure + complete_procedure + "
                "abort_procedure + hold_procedure handlers at __init__; only execute() is "
                "available without them."
            )
        envelope_kwargs: dict[str, Any] = {
            "principal_id": principal_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "surface_id": surface_id,
        }
        try:
            await self._start_procedure(
                StartProcedure(procedure_id=procedure_id), **envelope_kwargs
            )
        except _LIFECYCLE_RERAISE:
            raise
        except Exception as exc:
            return ConductorResult(
                procedure_id=procedure_id,
                completed_count=0,
                failure=ConductorFailure(
                    step_index=None,
                    source_kind=_SOURCE_KIND_LIFECYCLE,
                    target=_LIFECYCLE_TARGET_START,
                    error_class=type(exc).__name__,
                    message=str(exc),
                ),
            )
        # Mirror conduct(): a mid-execute cancellation best-effort aborts so the
        # FSM is not orphaned in Running, then re-raises. A cancellation is not a
        # recoverable step failure, so it aborts rather than pausing to Held.
        abort_procedure = self._abort_procedure
        async with abort_orphan_on_cancel(
            lambda: abort_procedure(
                AbortProcedure(procedure_id=procedure_id, reason="cancelled mid-execute"),
                **envelope_kwargs,
            )
        ):
            result = await self.execute(
                procedure_id=procedure_id,
                principal_id=principal_id,
                correlation_id=correlation_id,
                steps=steps,
                causation_id=causation_id,
                surface_id=surface_id,
            )
        actuation_kind = result.actuation_kind.value if result.actuation_kind is not None else None
        if result.succeeded:
            try:
                await self._complete_procedure(
                    CompleteProcedure(procedure_id=procedure_id, actuation_kind=actuation_kind),
                    **envelope_kwargs,
                )
            except _LIFECYCLE_RERAISE:
                raise
            except Exception as exc:
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=result.completed_count,
                    measurements=result.measurements,
                    artifacts=result.artifacts,
                    outputs=result.outputs,
                    failure=ConductorFailure(
                        step_index=None,
                        source_kind=_SOURCE_KIND_LIFECYCLE,
                        target=_LIFECYCLE_TARGET_COMPLETE,
                        error_class=type(exc).__name__,
                        message=str(exc),
                    ),
                )
            return result
        failure = result.failure
        assert failure is not None  # not result.succeeded implies failure
        if _is_recoverable_failure(failure):
            # Pause-to-Held instead of abort: a setpoint / check failure is
            # re-drivable / re-runnable, so keep the conduct resumable. The
            # hold is best-effort: if it fails, leave the Procedure Running
            # (held stays False) and surface the original step failure, the
            # same posture as conduct()'s best-effort abort that fails.
            held_ok = False
            with contextlib.suppress(Exception):
                await self._hold_procedure(
                    HoldProcedure(
                        procedure_id=procedure_id,
                        reason=_derive_failure_reason(failure),
                        # Carry the observed-so-far kind so a later reconduct
                        # folds the pre-hold provenance with the replay tail.
                        actuation_kind=actuation_kind,
                    ),
                    **envelope_kwargs,
                )
                held_ok = True
            if held_ok:
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=result.completed_count,
                    failure=failure,
                    actuation_kind=result.actuation_kind,
                    held=True,
                    measurements=result.measurements,
                    artifacts=result.artifacts,
                    outputs=result.outputs,
                )
            return result
        # Non-recoverable step failure (action): best-effort abort, exactly
        # like conduct(). Holding would strand a Procedure whose replay tail
        # starts with an interrupted acquisition.
        with contextlib.suppress(Exception):
            await self._abort_procedure(
                AbortProcedure(
                    procedure_id=procedure_id,
                    reason=_derive_failure_reason(failure),
                    actuation_kind=actuation_kind,
                ),
                **envelope_kwargs,
            )
        return result

    async def conduct_until_converged(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        convergence_capture_name: str,
        criterion: CheckCriterion,
        max_consecutive_unconverged_iterations: int | None = None,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        """Drive an iterate-measure-correct convergence loop over one pass block.

        The AUTO sibling of `conduct()` (slice 6c): where `conduct()` walks a
        step list ONCE then completes / aborts, this re-walks `steps` (ONE
        pass block) repeatedly until a loop-evaluated criterion over the
        captures bus is met, OR the patience cap trips. It owns the full FSM:
        `start_procedure` -> { `start_iteration` -> `execute(pass)` ->
        `end_iteration` } * -> `complete_procedure` | `abort_procedure`.

        `steps` is the per-pass block (NO terminal convergence CheckStep; it
        MAY carry ordinary in-block safety CheckSteps that keep NORMAL
        halt-on-fail). Inside one pass a deposit-`ComputeStep` writes the
        computed offset into `captures[convergence_capture_name]` and a
        same-pass `SetpointStep` `CaptureRef` drives the correction.

        CONVERGENCE is option C, loop-evaluated: after each SUCCESSFUL pass the
        loop reads `captures[convergence_capture_name]` and sets
        `converged = _criterion_matches(criterion, value)` (the EXISTING
        criterion union + matcher, reused as-is). There is NO walked
        convergence CheckStep, so a not-converged pass is not a step failure
        and the Procedure stays Running (NOT Held: this is a sibling of
        conduct, not try_conduct).

        CONTROL FLOW (B2/B3/B4):

          0. ABSOLUTE CEILING (defense-in-depth): at the loop top, if the pass
             count has reached `_ABSOLUTE_MAX_ITERATIONS`, STOP and abort with
             `AbsoluteIterationCeilingReached`. This applies EVEN WHEN the
             patience cap is None: each pass actuates hardware, so an uncapped
             loop with a never-matching criterion is bounded by this runaway
             backstop. No iteration is open at the loop top, so the abort is
             direct (like the cap pre-check).
          1. CAP PRE-CHECK (B2): when a cap is set and the consecutive
             unconverged streak has reached it, STOP and abort WITHOUT calling
             start_iteration (the planned terminal; avoids the deterministic
             ProcedureIterationLimitReachedError). A defensive try/except
             around start_iteration treats that error as a cap-trip backstop.
          2. start_iteration(index = iteration_count + 1).
          3. fresh per-pass captures dict; execute(pass, captures=...).
          4. on success: read the convergence value (loud-fail if the deposit
             nonetheless left it absent) and evaluate the criterion. On
             failure (real fault OR a legitimately-failing in-block safety
             CheckStep): end_iteration(converged=None) THEN abort, return the
             failure verbatim.
          5. end_iteration(converged) ALWAYS before any FSM transition (B3).
          6. converged -> complete; else loop.

        `current_iteration_index` is None on the converged-complete, cap-abort,
        absolute-ceiling-abort, failed-pass-abort, and absent-name-abort
        terminals, because every open iteration is closed via end_iteration
        before the terminal transition. The CANCELLATION terminal is the
        documented exception (mirroring reconduct's cancel carve-out):
        `abort_orphan_on_cancel` fires AbortProcedure while an iteration may
        still be open (no end_iteration on the cancel path), so
        `current_iteration_index` may be left set. The denorm is inert (the
        Procedure is terminal, Aborted) and `actuation_kind` is recorded None;
        an aborted Procedure promotes no Calibration, so the open-iteration
        denorm is benign. Threading end_iteration into the cancel lambda is too
        invasive for the inert benefit and is intentionally not done.

        Requires start_procedure + complete_procedure + abort_procedure +
        start_iteration + end_iteration handlers at __init__; raises
        RuntimeError (a wiring bug) otherwise.
        """
        if (
            self._start_procedure is None
            or self._complete_procedure is None
            or self._abort_procedure is None
            or self._start_iteration is None
            or self._end_iteration is None
        ):
            raise RuntimeError(
                "Conductor.conduct_until_converged() requires start_procedure + "
                "complete_procedure + abort_procedure + start_iteration + end_iteration "
                "handlers at __init__; only execute() is available without them."
            )
        envelope_kwargs: dict[str, Any] = {
            "principal_id": principal_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "surface_id": surface_id,
        }
        try:
            await self._start_procedure(
                StartProcedure(procedure_id=procedure_id), **envelope_kwargs
            )
        except _LIFECYCLE_RERAISE:
            raise
        except Exception as exc:
            return ConductorResult(
                procedure_id=procedure_id,
                completed_count=0,
                failure=ConductorFailure(
                    step_index=None,
                    source_kind=_SOURCE_KIND_LIFECYCLE,
                    target=_LIFECYCLE_TARGET_START,
                    error_class=type(exc).__name__,
                    message=str(exc),
                ),
            )
        abort_procedure = self._abort_procedure
        async with abort_orphan_on_cancel(
            lambda: abort_procedure(
                AbortProcedure(procedure_id=procedure_id, reason="cancelled mid-execute"),
                **envelope_kwargs,
            )
        ):
            return await self._run_convergence_loop(
                procedure_id=procedure_id,
                steps=steps,
                convergence_capture_name=convergence_capture_name,
                criterion=criterion,
                max_consecutive_unconverged_iterations=max_consecutive_unconverged_iterations,
                envelope_kwargs=envelope_kwargs,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
            )

    async def _run_convergence_loop(
        self,
        *,
        procedure_id: UUID,
        steps: Sequence[Step],
        convergence_capture_name: str,
        criterion: CheckCriterion,
        max_consecutive_unconverged_iterations: int | None,
        envelope_kwargs: dict[str, Any],
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
        surface_id: UUID,
    ) -> ConductorResult:
        """The post-start convergence loop body of `conduct_until_converged`.

        Extracted so the cap pre-check / start_iteration / execute /
        end_iteration sequencing is one linear read. The Procedure is already
        Running (start_procedure succeeded). Returns the terminal
        ConductorResult after completing (converged) or aborting (cap-trip /
        in-pass fault). The streak + iteration_count are tracked locally: the
        loop owns every iteration boundary for this conduct, so it knows each
        pass's verdict without re-loading aggregate state."""
        assert self._complete_procedure is not None  # guarded by caller
        assert self._abort_procedure is not None
        assert self._start_iteration is not None
        assert self._end_iteration is not None
        cap = max_consecutive_unconverged_iterations
        iteration_count = 0
        streak = 0
        last_result: ConductorResult | None = None
        folded_kind: str | None = None
        while True:
            # ABSOLUTE CEILING (defense-in-depth): bites even when cap is None.
            # No iteration is open at the loop top, so abort directly (like the
            # cap pre-check). Guards a never-matching criterion with no patience
            # cap from actuating hardware without bound.
            if iteration_count >= _ABSOLUTE_MAX_ITERATIONS:
                return await self._abort_absolute_ceiling(
                    procedure_id=procedure_id,
                    iteration_count=iteration_count,
                    folded_kind=folded_kind,
                    last_result=last_result,
                    envelope_kwargs=envelope_kwargs,
                )
            # CAP PRE-CHECK (B2): a cap of C permits exactly C consecutive
            # unconverged passes; stop before the (C+1)-th start_iteration
            # rather than letting the decider 409.
            if cap is not None and streak >= cap:
                return await self._abort_unconverged_cap(
                    procedure_id=procedure_id,
                    streak=streak,
                    cap=cap,
                    folded_kind=folded_kind,
                    last_result=last_result,
                    envelope_kwargs=envelope_kwargs,
                )
            next_index = iteration_count + 1
            try:
                await self._start_iteration(
                    StartProcedureIteration(procedure_id=procedure_id, iteration_index=next_index),
                    **envelope_kwargs,
                )
            except ProcedureIterationLimitReachedError:  # pragma: no cover
                # Defensive backstop (B2): UNREACHABLE given the local-streak /
                # aggregate-iteration lockstep + the cap pre-check above, which
                # stops before the (C+1)-th start_iteration. Kept as
                # intentional defense-in-depth: if the aggregate refused the
                # next iteration on the cap, no iteration was opened, so abort
                # directly.
                return await self._abort_unconverged_cap(
                    procedure_id=procedure_id,
                    streak=streak,
                    cap=cap if cap is not None else streak,
                    folded_kind=folded_kind,
                    last_result=last_result,
                    envelope_kwargs=envelope_kwargs,
                )
            iteration_count += 1
            pass_captures: dict[str, Any] = {}
            result = await self.execute(
                procedure_id=procedure_id,
                principal_id=principal_id,
                correlation_id=correlation_id,
                steps=steps,
                causation_id=causation_id,
                surface_id=surface_id,
                captures=pass_captures,
            )
            last_result = result
            folded_kind = merge_actuation_kinds(
                folded_kind,
                result.actuation_kind.value if result.actuation_kind is not None else None,
            )
            if not result.succeeded:
                # Real fault OR a legitimately-failing in-block safety check:
                # close the open iteration (B3, converged=None = no verdict)
                # then abort, surfacing the step failure verbatim.
                await self._end_iteration(
                    EndProcedureIteration(
                        procedure_id=procedure_id,
                        iteration_index=next_index,
                        converged=None,
                        reason=_derive_failure_reason(result.failure)
                        if result.failure is not None
                        else None,
                    ),
                    **envelope_kwargs,
                )
                await self._abort_after_failed_pass(
                    procedure_id=procedure_id,
                    failure=result.failure,
                    folded_kind=folded_kind,
                    envelope_kwargs=envelope_kwargs,
                )
                return replace(
                    result,
                    actuation_kind=(
                        ActuationKind(folded_kind) if folded_kind is not None else None
                    ),
                )
            if convergence_capture_name not in pass_captures:
                # A successful pass GUARANTEES the deposit ran (the C1 loud-fails
                # would otherwise have halted the pass); an absent name here is
                # an authoring error (the pass block declares no deposit into
                # this name). Loud-fail: close the iteration then abort.
                msg = (
                    f"convergence capture {convergence_capture_name!r} was not deposited "
                    f"by the pass block (available: {sorted(pass_captures)})"
                )
                await self._end_iteration(
                    EndProcedureIteration(
                        procedure_id=procedure_id,
                        iteration_index=next_index,
                        converged=None,
                        reason=msg[:REASON_MAX_LENGTH],
                    ),
                    **envelope_kwargs,
                )
                failure = ConductorFailure(
                    step_index=None,
                    source_kind=_STEP_KIND_COMPUTE,
                    target=convergence_capture_name,
                    error_class=_ERROR_MEASUREMENT_NOT_FOUND,
                    message=msg,
                )
                await self._abort_after_failed_pass(
                    procedure_id=procedure_id,
                    failure=failure,
                    folded_kind=folded_kind,
                    envelope_kwargs=envelope_kwargs,
                )
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=result.completed_count,
                    failure=failure,
                    actuation_kind=(
                        ActuationKind(folded_kind) if folded_kind is not None else None
                    ),
                    measurements=result.measurements,
                )
            converged = _criterion_matches(criterion, pass_captures[convergence_capture_name])
            await self._end_iteration(
                EndProcedureIteration(
                    procedure_id=procedure_id,
                    iteration_index=next_index,
                    converged=converged,
                    reason=None,
                ),
                **envelope_kwargs,
            )
            if converged:
                return await self._complete_converged(
                    procedure_id=procedure_id,
                    result=result,
                    folded_kind=folded_kind,
                    envelope_kwargs=envelope_kwargs,
                )
            streak += 1

    async def _complete_converged(
        self,
        *,
        procedure_id: UUID,
        result: ConductorResult,
        folded_kind: str | None,
        envelope_kwargs: dict[str, Any],
    ) -> ConductorResult:
        """Complete a converged convergence loop; mirror conduct()'s complete arm."""
        assert self._complete_procedure is not None
        merged = replace(
            result,
            actuation_kind=ActuationKind(folded_kind) if folded_kind is not None else None,
        )
        try:
            await self._complete_procedure(
                CompleteProcedure(procedure_id=procedure_id, actuation_kind=folded_kind),
                **envelope_kwargs,
            )
        except _LIFECYCLE_RERAISE:
            raise
        except Exception as exc:
            return ConductorResult(
                procedure_id=procedure_id,
                completed_count=result.completed_count,
                measurements=result.measurements,
                failure=ConductorFailure(
                    step_index=None,
                    source_kind=_SOURCE_KIND_LIFECYCLE,
                    target=_LIFECYCLE_TARGET_COMPLETE,
                    error_class=type(exc).__name__,
                    message=str(exc),
                ),
            )
        return merged

    async def _abort_unconverged_cap(
        self,
        *,
        procedure_id: UUID,
        streak: int,
        cap: int,
        folded_kind: str | None,
        last_result: ConductorResult | None,
        envelope_kwargs: dict[str, Any],
    ) -> ConductorResult:
        """Abort a convergence loop that exhausted its patience cap (B2 terminal).

        No iteration is open here (the pre-check stops BEFORE start_iteration,
        and the backstop fires when start_iteration itself refused), so the
        abort is the only FSM transition and current_iteration_index is
        already None. The result carries a lifecycle ConductorFailure naming
        the cap so the caller can distinguish never-converged from a fault."""
        assert self._abort_procedure is not None
        msg = (
            f"convergence loop gave up after {streak} consecutive unconverged "
            f"iterations (cap {cap})"
        )
        reason = msg[:REASON_MAX_LENGTH]
        with contextlib.suppress(Exception):
            await self._abort_procedure(
                AbortProcedure(
                    procedure_id=procedure_id, reason=reason, actuation_kind=folded_kind
                ),
                **envelope_kwargs,
            )
        completed_count = last_result.completed_count if last_result is not None else 0
        measurements = last_result.measurements if last_result is not None else ()
        return ConductorResult(
            procedure_id=procedure_id,
            completed_count=completed_count,
            failure=ConductorFailure(
                step_index=None,
                source_kind=_SOURCE_KIND_LIFECYCLE,
                target=_LIFECYCLE_TARGET_ABORT,
                error_class=_ERROR_ITERATION_CAP_REACHED,
                message=msg,
            ),
            actuation_kind=ActuationKind(folded_kind) if folded_kind is not None else None,
            measurements=measurements,
        )

    async def _abort_absolute_ceiling(
        self,
        *,
        procedure_id: UUID,
        iteration_count: int,
        folded_kind: str | None,
        last_result: ConductorResult | None,
        envelope_kwargs: dict[str, Any],
    ) -> ConductorResult:
        """Abort a convergence loop that hit the absolute iteration ceiling.

        Mirrors `_abort_unconverged_cap`: the check fires at the loop top with no
        iteration open, so the abort is the only FSM transition and
        current_iteration_index is already None. Distinct error_class
        (`AbsoluteIterationCeilingReached`) so the caller can tell a runaway
        backstop from an operator-set patience cap. Applies even when no patience
        cap was supplied (cap is None)."""
        assert self._abort_procedure is not None
        msg = (
            f"convergence loop hit the absolute iteration ceiling "
            f"({iteration_count} of {_ABSOLUTE_MAX_ITERATIONS})"
        )
        reason = msg[:REASON_MAX_LENGTH]
        with contextlib.suppress(Exception):
            await self._abort_procedure(
                AbortProcedure(
                    procedure_id=procedure_id, reason=reason, actuation_kind=folded_kind
                ),
                **envelope_kwargs,
            )
        completed_count = last_result.completed_count if last_result is not None else 0
        measurements = last_result.measurements if last_result is not None else ()
        return ConductorResult(
            procedure_id=procedure_id,
            completed_count=completed_count,
            failure=ConductorFailure(
                step_index=None,
                source_kind=_SOURCE_KIND_LIFECYCLE,
                target=_LIFECYCLE_TARGET_ABORT,
                error_class=_ERROR_ABSOLUTE_ITERATION_CEILING,
                message=msg,
            ),
            actuation_kind=ActuationKind(folded_kind) if folded_kind is not None else None,
            measurements=measurements,
        )

    async def _abort_after_failed_pass(
        self,
        *,
        procedure_id: UUID,
        failure: ConductorFailure | None,
        folded_kind: str | None,
        envelope_kwargs: dict[str, Any],
    ) -> None:
        """Best-effort abort after a failed pass (the open iteration is already closed).

        Mirrors conduct()'s best-effort abort: if the abort itself fails, the
        original step failure is what surfaces to the caller."""
        assert self._abort_procedure is not None
        reason = (
            _derive_failure_reason(failure)
            if failure is not None
            else "convergence pass failed"[:REASON_MAX_LENGTH]
        )
        with contextlib.suppress(Exception):
            await self._abort_procedure(
                AbortProcedure(
                    procedure_id=procedure_id, reason=reason, actuation_kind=folded_kind
                ),
                **envelope_kwargs,
            )

    async def conduct_until_advised(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        decide_port: DecidePort,
        objective: SteeringObjective,
        space: SteeringSpace,
        objective_capture_name: str,
        point_to_captures: Callable[[SteeringPoint], dict[str, Any]],
        budget: SteeringBudget | None = None,
        record_turn: Callable[[SteeringAdvice, SteeringObservation, int], Awaitable[None]]
        | None = None,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        """Drive an autonomous measure-then-advise loop steered by a `DecidePort`.

        The DECIDE-axis twin of `conduct_until_converged`: where the
        convergence loop evaluates a fixed criterion over the captures bus
        after each pass, this hands the accumulated evidence to an external
        brain (`decide_port.advise_next`) and lets the brain decide where to
        measure next or whether to stop. It owns the same full FSM:
        `start_procedure` -> { `start_iteration` -> `execute(pass)` ->
        `advise_next` -> `end_iteration` } * -> `complete_procedure`
        (brain advised Stop) | `abort_procedure` (a pass faulted, the brain
        raised, or the absolute ceiling tripped).

        `steps` is the per-pass block; the same authored block runs every
        pass. The keystone is SEED-THE-CAPTURES: a brain-proposed
        `SteeringPoint` is translated by `point_to_captures` into a captures
        dict that is seeded into the per-pass bus BEFORE `execute`, so the
        block's `SetpointStep` `CaptureRef`s resolve to the advised
        coordinates. The objective scalar a brain reads is deposited by the
        block under `objective_capture_name` (a `ComputeStep` / `CaptureStep`
        deposit) and surfaced into the observation handed to the next call.

        LOOP ORDER is measure-then-advise: pass 1 has no advice yet, so it
        seeds the space's authored-default position (the probe: each axis at
        its lower bound, else its first choice) and measures there; the result
        is observed and the brain's advice seeds pass 2 onward. The brain
        decides Stop after seeing pass 1, so a one-pass campaign is
        expressible. Each observation records the point it measured at, so a
        stateful brain rebuilt from the history sees real coordinates.

        VERDICT mapping: every steering pass closes its iteration with
        `converged=None` (a steering pass has no convergence verdict, so the
        aggregate's convergence streak never bites) and `advised_stop` set to
        whether the brain said Stop, plus the advice provenance
        (`advice_to_audit_fields`) for the in-conductor audit ledger. A Stop
        completes; a Measure seeds the next pass with `advice.next_point`.

        FOLDING a brain fault: when `advise_next` raises a `Decide*Error` the
        loop closes the open iteration (`converged=None`, `advised_stop=None`,
        reason = the brain's message) then aborts, surfacing the brain's
        `error_class` on a `decide`-source `ConductorFailure`, per the port's
        "fold a raised exception into a recorded steering decision rather than
        crashing the loop". A non-`Decide*Error` propagates.

        `budget` is threaded informationally into the `SteeringEvidence` the
        brain weighs; it is NOT enforced in the loop at this slice (budget
        exhaustion is a normal non-error end the brain signals via Stop, not a
        caller-side abort). The only loop backstop is the absolute iteration
        ceiling (`_ABSOLUTE_MAX_ITERATIONS`), reused verbatim from the
        convergence twin, which bounds a brain that never advises Stop.

        `record_turn`, when supplied, is awaited per pass with the advice, the
        observation, and the 0-based loop turn; the route / tool pass None (the
        provenance already lands on the iteration ledger).

        Requires start_procedure + complete_procedure + abort_procedure +
        start_iteration + end_iteration handlers at __init__; raises
        RuntimeError (a wiring bug) otherwise.
        """
        if (
            self._start_procedure is None
            or self._complete_procedure is None
            or self._abort_procedure is None
            or self._start_iteration is None
            or self._end_iteration is None
        ):
            raise RuntimeError(
                "Conductor.conduct_until_advised() requires start_procedure + "
                "complete_procedure + abort_procedure + start_iteration + end_iteration "
                "handlers at __init__; only execute() is available without them."
            )
        self._validate_steering_wire(
            steps=steps,
            space=space,
            objective_capture_name=objective_capture_name,
            point_to_captures=point_to_captures,
        )
        envelope_kwargs: dict[str, Any] = {
            "principal_id": principal_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "surface_id": surface_id,
        }
        try:
            await self._start_procedure(
                StartProcedure(procedure_id=procedure_id), **envelope_kwargs
            )
        except _LIFECYCLE_RERAISE:
            raise
        except Exception as exc:
            return ConductorResult(
                procedure_id=procedure_id,
                completed_count=0,
                failure=ConductorFailure(
                    step_index=None,
                    source_kind=_SOURCE_KIND_LIFECYCLE,
                    target=_LIFECYCLE_TARGET_START,
                    error_class=type(exc).__name__,
                    message=str(exc),
                ),
            )
        abort_procedure = self._abort_procedure
        async with abort_orphan_on_cancel(
            lambda: abort_procedure(
                AbortProcedure(procedure_id=procedure_id, reason="cancelled mid-execute"),
                **envelope_kwargs,
            )
        ):
            return await self._run_decide_loop(
                procedure_id=procedure_id,
                steps=steps,
                decide_port=decide_port,
                objective=objective,
                space=space,
                objective_capture_name=objective_capture_name,
                point_to_captures=point_to_captures,
                budget=budget,
                record_turn=record_turn,
                envelope_kwargs=envelope_kwargs,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
            )

    def _validate_steering_wire(
        self,
        *,
        steps: Sequence[Step],
        space: SteeringSpace,
        objective_capture_name: str,
        point_to_captures: Callable[[SteeringPoint], dict[str, Any]],
    ) -> None:
        """Wire-time guard for `conduct_until_advised`; raises `ValueError` on a mis-wire.

        These are programmer / authoring errors (the static block, the space,
        and the caller's `point_to_captures` do not line up), so they raise
        BEFORE any FSM event rather than folding into a recorded outcome.

        COVERAGE: every `SteeringAxis.name` the brain may propose must be
        consumed by some `SetpointStep` `CaptureRef` in the block, otherwise a
        seeded coordinate would never reach actuation.

        DISJOINTNESS: the keys `point_to_captures` seeds must not collide with
        the objective slot or with any slot the block itself deposits (a
        `CaptureStep` / `ComputeStep` `capture_name`), and must cover exactly
        the axis names, otherwise a seed would overwrite a measured slot or
        leave a `CaptureRef` unresolved.
        """
        declared_capture_refs = {
            step.value.capture_name
            for step in steps
            if isinstance(step, SetpointStep) and isinstance(step.value, CaptureRef)
        }
        for axis in space.axes:
            if axis.name not in declared_capture_refs:
                raise ValueError(
                    f"steering axis {axis.name!r} is not consumed by any SetpointStep "
                    "CaptureRef in the static block"
                )
        probe = _steering_probe_point(space)
        seeded_keys = set(point_to_captures(probe))
        deposited = {step.capture_name for step in steps if isinstance(step, CaptureStep)} | {
            step.capture_name
            for step in steps
            if isinstance(step, ComputeStep) and step.capture_name is not None
        }
        if objective_capture_name in seeded_keys:
            raise ValueError(
                f"point_to_captures seeds the objective slot {objective_capture_name!r}; "
                "the objective is measured, not seeded"
            )
        overlap = seeded_keys & deposited
        if overlap:
            raise ValueError(
                f"point_to_captures seeds slot(s) {sorted(overlap)!r} the static block "
                "also deposits; a seed would overwrite a measured value"
            )
        axis_names = {axis.name for axis in space.axes}
        if seeded_keys != axis_names:
            raise ValueError(
                f"point_to_captures keys {sorted(seeded_keys)!r} must cover exactly the "
                f"steering axis names {sorted(axis_names)!r}"
            )

    async def _run_decide_loop(
        self,
        *,
        procedure_id: UUID,
        steps: Sequence[Step],
        decide_port: DecidePort,
        objective: SteeringObjective,
        space: SteeringSpace,
        objective_capture_name: str,
        point_to_captures: Callable[[SteeringPoint], dict[str, Any]],
        budget: SteeringBudget | None,
        record_turn: Callable[[SteeringAdvice, SteeringObservation, int], Awaitable[None]] | None,
        envelope_kwargs: dict[str, Any],
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
        surface_id: UUID,
    ) -> ConductorResult:
        """The post-start decide loop body of `conduct_until_advised`.

        Twin of `_run_convergence_loop`: extracted so the start_iteration /
        seed / execute / advise / end_iteration sequencing is one linear read.
        The Procedure is already Running. Returns the terminal ConductorResult
        after the brain advised Stop (complete), a pass faulted or the brain
        raised (abort), or the absolute ceiling tripped (abort). The
        observation history + the pending point are tracked locally: the loop
        owns every iteration boundary, so it reconstructs the evidence each
        pass without re-loading aggregate state.

        REPLAY DETERMINISM: because the loop is pure in-process state from
        iteration 0 (it never reads the event store) and the one-pass block is
        pinned once and re-walked verbatim, re-driving it over identical inputs
        with a brain whose advice is a pure function of the evidence reproduces
        the run byte for byte: the same iteration boundaries, the same seeded
        coordinates, the same advice provenance, and the same terminal. Both
        shipped adapters are such brains, so the advised next_point is NOT
        recorded on the iteration ledger; determinism comes from the stateless
        brain plus the pinned block, not from a persisted coordinate. Re-seeding
        a RECORDED next_point for already-closed passes and consulting the brain
        only at the open frontier (so a NON-deterministic brain, a real GP /
        gpCAM / LLM, is not re-queried on replay) is a deferred leg: it needs
        three additive pieces together (an advised_next_point field on the
        iteration event, a decide-loop resume entry, and a ValueCaptured
        observation-replay channel) and is earned WITH that first
        non-deterministic adapter."""
        assert self._complete_procedure is not None  # guarded by caller
        assert self._abort_procedure is not None
        assert self._start_iteration is not None
        assert self._end_iteration is not None
        iteration_count = 0
        last_result: ConductorResult | None = None
        folded_kind: str | None = None
        observations: list[SteeringObservation] = []
        pending_point: SteeringPoint | None = None
        while True:
            if iteration_count >= _ABSOLUTE_MAX_ITERATIONS:
                return await self._abort_absolute_ceiling(
                    procedure_id=procedure_id,
                    iteration_count=iteration_count,
                    folded_kind=folded_kind,
                    last_result=last_result,
                    envelope_kwargs=envelope_kwargs,
                )
            next_index = iteration_count + 1
            await self._start_iteration(
                StartProcedureIteration(procedure_id=procedure_id, iteration_index=next_index),
                **envelope_kwargs,
            )
            iteration_count += 1
            pass_captures: dict[str, Any] = {}
            # SEED-THE-CAPTURES keystone: each pass seeds the point it will
            # measure into the captures bus before execute() so the block's
            # SetpointStep CaptureRefs resolve to those coordinates. Pass 1 has
            # no advice yet, so it seeds the space's authored-default position
            # (the probe); pass 2+ seed the brain's advised point. The
            # observation then records seed_point, so every observation's
            # coordinates are where it actually measured.
            seed_point = (
                pending_point if pending_point is not None else _steering_probe_point(space)
            )
            pass_captures.update(point_to_captures(seed_point))
            result = await self.execute(
                procedure_id=procedure_id,
                principal_id=principal_id,
                correlation_id=correlation_id,
                steps=steps,
                causation_id=causation_id,
                surface_id=surface_id,
                captures=pass_captures,
            )
            last_result = result
            folded_kind = merge_actuation_kinds(
                folded_kind,
                result.actuation_kind.value if result.actuation_kind is not None else None,
            )
            if not result.succeeded:
                await self._end_iteration(
                    EndProcedureIteration(
                        procedure_id=procedure_id,
                        iteration_index=next_index,
                        converged=None,
                        reason=_derive_failure_reason(result.failure)
                        if result.failure is not None
                        else None,
                    ),
                    **envelope_kwargs,
                )
                await self._abort_after_failed_pass(
                    procedure_id=procedure_id,
                    failure=result.failure,
                    folded_kind=folded_kind,
                    envelope_kwargs=envelope_kwargs,
                )
                return replace(
                    result,
                    actuation_kind=(
                        ActuationKind(folded_kind) if folded_kind is not None else None
                    ),
                )
            if objective_capture_name not in pass_captures:
                msg = (
                    f"objective capture {objective_capture_name!r} was not deposited "
                    f"by the pass block (available: {sorted(pass_captures)})"
                )
                await self._end_iteration(
                    EndProcedureIteration(
                        procedure_id=procedure_id,
                        iteration_index=next_index,
                        converged=None,
                        reason=msg[:REASON_MAX_LENGTH],
                    ),
                    **envelope_kwargs,
                )
                failure = ConductorFailure(
                    step_index=None,
                    source_kind=_STEP_KIND_COMPUTE,
                    target=objective_capture_name,
                    error_class=_ERROR_MEASUREMENT_NOT_FOUND,
                    message=msg,
                )
                await self._abort_after_failed_pass(
                    procedure_id=procedure_id,
                    failure=failure,
                    folded_kind=folded_kind,
                    envelope_kwargs=envelope_kwargs,
                )
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=result.completed_count,
                    failure=failure,
                    actuation_kind=(
                        ActuationKind(folded_kind) if folded_kind is not None else None
                    ),
                    measurements=result.measurements,
                )
            observation = SteeringObservation(
                point=seed_point,
                measurements=result.measurements,
                artifact_ref=None,
                actuation_kind=result.actuation_kind,
                succeeded=result.succeeded,
            )
            observations.append(observation)
            evidence = SteeringEvidence(
                objective=objective,
                space=space,
                observations=tuple(observations),
                budget=budget if budget is not None else SteeringBudget(),
                iteration_index=iteration_count - 1,
                procedure_id=procedure_id,
            )
            try:
                advice = await decide_port.advise_next(evidence)
                if advice.verdict is SteeringVerdict.MEASURE:
                    _validate_advice_point(advice.next_point, space)
            except _DECIDE_ERRORS as exc:
                await self._end_iteration(
                    EndProcedureIteration(
                        procedure_id=procedure_id,
                        iteration_index=next_index,
                        converged=None,
                        reason=str(exc)[:REASON_MAX_LENGTH],
                        advised_stop=None,
                    ),
                    **envelope_kwargs,
                )
                failure = ConductorFailure(
                    step_index=None,
                    source_kind=_SOURCE_KIND_DECIDE,
                    target=objective_capture_name,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                await self._abort_after_failed_pass(
                    procedure_id=procedure_id,
                    failure=failure,
                    folded_kind=folded_kind,
                    envelope_kwargs=envelope_kwargs,
                )
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=result.completed_count,
                    failure=failure,
                    actuation_kind=(
                        ActuationKind(folded_kind) if folded_kind is not None else None
                    ),
                    measurements=result.measurements,
                )
            audit = advice_to_audit_fields(advice)
            await self._end_iteration(
                EndProcedureIteration(
                    procedure_id=procedure_id,
                    iteration_index=next_index,
                    converged=None,
                    reason=None,
                    advised_stop=advice.verdict is SteeringVerdict.STOP,
                    reasoning=audit.reasoning,
                    confidence=audit.confidence,
                    confidence_source=audit.confidence_source,
                    alternatives=audit.alternatives,
                    model_ref=audit.model_ref,
                ),
                **envelope_kwargs,
            )
            if record_turn is not None:
                await record_turn(advice, observation, iteration_count - 1)
            if advice.verdict is SteeringVerdict.STOP:
                return await self._complete_advised(
                    procedure_id=procedure_id,
                    result=result,
                    folded_kind=folded_kind,
                    envelope_kwargs=envelope_kwargs,
                )
            pending_point = advice.next_point

    async def _complete_advised(
        self,
        *,
        procedure_id: UUID,
        result: ConductorResult,
        folded_kind: str | None,
        envelope_kwargs: dict[str, Any],
    ) -> ConductorResult:
        """Complete a brain-advised-Stop steering loop; thin twin of `_complete_converged`."""
        assert self._complete_procedure is not None
        merged = replace(
            result,
            actuation_kind=ActuationKind(folded_kind) if folded_kind is not None else None,
        )
        try:
            await self._complete_procedure(
                CompleteProcedure(procedure_id=procedure_id, actuation_kind=folded_kind),
                **envelope_kwargs,
            )
        except _LIFECYCLE_RERAISE:
            raise
        except Exception as exc:
            return ConductorResult(
                procedure_id=procedure_id,
                completed_count=result.completed_count,
                measurements=result.measurements,
                failure=ConductorFailure(
                    step_index=None,
                    source_kind=_SOURCE_KIND_LIFECYCLE,
                    target=_LIFECYCLE_TARGET_COMPLETE,
                    error_class=type(exc).__name__,
                    message=str(exc),
                ),
            )
        return merged

    async def reconduct(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        boundary: int,
        prior_actuation_kind: str | None = None,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ConductorResult:
        """Resume a Held Procedure and REPLAY its pinned resolved steps from `boundary`.

        The resume twin of `conduct()`: where `conduct()` drives
        start -> execute -> complete | abort, this drives
        resume -> execute_from -> complete | (leave Running) | abort.

          1. Issue `resume_procedure` (transitions Held -> Running). Its OWN
             authz + off-diagonal parent-Run-Held guard fire here; a non-Held
             Procedure or a held parent Run raises `ProcedureCannotResumeError`
             which PROPAGATES (mapped to 409 at the route) rather than landing
             in the result body. A refused resume is a guard outcome, not a
             replay outcome, and no replay has happened yet.
          2. Call `self.execute_from(steps, boundary)`: re-drive setpoints,
             re-run checks, halt-for-operator on an acquisition.
          3. Terminalize three-way:
               - clean tail (incl. empty) -> `complete_procedure` (Completed).
               - acquisition halt -> NO transition; the Procedure stays Running
                 and the operator decides redo-fresh vs reseed from the result.
               - genuine step failure -> best-effort `abort_procedure` (if the
                 abort itself fails, the original step failure is what
                 surfaces, mirroring `conduct()`).

        `steps` is the parsed `ResolvedStepsRecorded.resolved_steps`: the
        caller locates + parses the PINNED record (resume NEVER re-derives the
        step list). `boundary` is single-sourced: it rides into both
        `ProcedureResumed.re_establishment_boundary` (audit) and
        `execute_from(boundary=...)` (replay).

        Requires `resume_procedure` + `complete_procedure` + `abort_procedure`
        handlers at __init__; raises `RuntimeError` (a wiring bug) otherwise.

        Unlike `conduct()`, this does NOT best-effort-abort on a mid-replay
        `CancelledError`: a cancellation after the resume leaves the Procedure
        Running with partial replay history, the same posture as the
        acquisition-halt branch (the operator reconciles). See
        [[project_resumable_conduct_design]] Tier 1.
        """
        if (
            self._resume_procedure is None
            or self._complete_procedure is None
            or self._abort_procedure is None
        ):
            raise RuntimeError(
                "Conductor.reconduct() requires resume_procedure + complete_procedure + "
                "abort_procedure handlers at __init__; only execute_from() is available "
                "without them."
            )
        envelope_kwargs: dict[str, Any] = {
            "principal_id": principal_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "surface_id": surface_id,
        }
        # Held -> Running. Refusals (not-Held / held parent Run / authz deny /
        # not-found) propagate to the route as their mapped HTTP codes; no
        # replay has happened, so they are NOT swallowed into the result body.
        await self._resume_procedure(
            ResumeProcedure(procedure_id=procedure_id, re_establishment_boundary=boundary),
            **envelope_kwargs,
        )
        result = await self.execute_from(
            procedure_id=procedure_id,
            principal_id=principal_id,
            correlation_id=correlation_id,
            steps=steps,
            boundary=boundary,
            causation_id=causation_id,
            surface_id=surface_id,
        )
        # Fold the pre-hold conduct's kind (carried on the Held procedure,
        # passed in by the handler) with the replay tail's observed kind, so a
        # boundary>0 resume past a simulated prefix does not complete as
        # Physical and bypass the promote_dataset gate. boundary=0 re-observes
        # everything, so the merge is a no-op there.
        tail_actuation_kind = (
            result.actuation_kind.value if result.actuation_kind is not None else None
        )
        actuation_kind = merge_actuation_kinds(prior_actuation_kind, tail_actuation_kind)
        # Report the merged kind on the result too, so the response body matches
        # the kind threaded onto the terminal event (not just the replay tail).
        merged_result = replace(
            result,
            actuation_kind=(ActuationKind(actuation_kind) if actuation_kind is not None else None),
        )
        if result.succeeded:
            # Clean tail (incl. empty tail): auto-complete, threading the
            # merged observed kind onto ProcedureCompleted (Data BC gate carrier).
            try:
                await self._complete_procedure(
                    CompleteProcedure(procedure_id=procedure_id, actuation_kind=actuation_kind),
                    **envelope_kwargs,
                )
            except _LIFECYCLE_RERAISE:
                raise
            except Exception as exc:
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=result.completed_count,
                    measurements=result.measurements,
                    artifacts=result.artifacts,
                    outputs=result.outputs,
                    failure=ConductorFailure(
                        step_index=None,
                        source_kind=_SOURCE_KIND_LIFECYCLE,
                        target=_LIFECYCLE_TARGET_COMPLETE,
                        error_class=type(exc).__name__,
                        message=str(exc),
                    ),
                )
            return merged_result
        if is_acquisition_halt(result.failure):
            # Halt-for-operator: leave the Procedure Running; no transition.
            # RESIDUAL: the replay tail's observed kind is NOT persisted here
            # (no terminal event), so a later manual complete/abort -- which
            # SETs actuation_kind from the command, not merges -- could stamp
            # over a tail simulator touch. Narrower than the hold->resume gap
            # this method closes; the design-memo second-writer hazard, aligned
            # with the Tier-2 acquisition-decomposition deferral.
            return merged_result
        # Genuine step failure: best-effort abort (if abort itself fails, the
        # original step failure is what surfaces). Mirrors conduct().
        failure = result.failure
        assert failure is not None  # not succeeded + not halt -> failure
        with contextlib.suppress(Exception):
            await self._abort_procedure(
                AbortProcedure(
                    procedure_id=procedure_id,
                    reason=_derive_failure_reason(failure),
                    actuation_kind=actuation_kind,
                ),
                **envelope_kwargs,
            )
        return merged_result

    async def _dispatch(
        self,
        step: Step,
        *,
        index: int,
        envelope: "_Envelope",
        port: ControlPort,
        captures: dict[str, Any],
        outputs: dict[str, ArtifactRef],
        compute: "_ComputeAccumulator",
    ) -> ConductorFailure | None:
        """Run one step + record outcome; return ConductorFailure on halt-condition.

        `port` is the per-conduct observing wrapper around the
        Conductor's ControlPort; every dispatch goes through it so
        actuation provenance is captured once for the whole conduct.
        `captures` is the per-conduct slot dict: a `CaptureStep` fills it,
        a `SetpointStep` with a `CaptureRef` value reads it, and a
        `ComputeStep` with a `capture_name` deposits its produced scalar into
        it (slice 6c chaining). `outputs` is the per-conduct artifact bus: a
        file-arm `ComputeStep` with an `output_ref_name` deposits its
        `ArtifactRef` into it, and a later `ComputeStep` with an `OutputRef`
        input reads it (compute-branch chaining). `compute` is the per-conduct
        accumulator a `ComputeStep` appends its produced `Measurement`s + folds
        its `ActuationKind` into (so `execute` can surface the values + the
        honest aggregate kind on the result).
        """
        if isinstance(step, SetpointStep):
            return await self._run_setpoint(
                step, index=index, envelope=envelope, port=port, captures=captures
            )
        if isinstance(step, ActionStep):
            return await self._run_action(step, index=index, envelope=envelope, port=port)
        if isinstance(step, CaptureStep):
            return await self._run_capture(
                step, index=index, envelope=envelope, port=port, captures=captures
            )
        if isinstance(step, ComputeStep):
            return await self._run_compute(
                step,
                index=index,
                envelope=envelope,
                compute=compute,
                captures=captures,
                outputs=outputs,
            )
        return await self._run_check(step, index=index, envelope=envelope, port=port)

    async def _run_setpoint(
        self,
        step: SetpointStep,
        *,
        index: int,
        envelope: "_Envelope",
        port: ControlPort,
        captures: dict[str, Any],
    ) -> ConductorFailure | None:
        # Resolve a CaptureRef value against the per-conduct captures BEFORE
        # any effect: an unseeded ref (e.g. resumed past the capturing step)
        # loud-fails with a recorded entry, no marker, nothing actuated.
        value = step.value
        if isinstance(value, CaptureRef):
            if value.capture_name not in captures:
                msg = (
                    f"setpoint at {step.address!r} references capture "
                    f"{value.capture_name!r} not captured before this step"
                )
                await self._record(
                    envelope=envelope,
                    index=index,
                    step_kind=_STEP_KIND_SETPOINT,
                    body={"address": step.address, "capture_ref": value.capture_name},
                    result=_RESULT_FAILED,
                    error_class=_ERROR_UNRESOLVED_CAPTURE,
                    message=msg,
                )
                return ConductorFailure(
                    step_index=index,
                    source_kind=_STEP_KIND_SETPOINT,
                    target=step.address,
                    error_class=_ERROR_UNRESOLVED_CAPTURE,
                    message=msg,
                )
            resolved: Any = captures[value.capture_name]
            payload_body: dict[str, Any] = {
                "address": step.address,
                "value": resolved,
                "capture_ref": value.capture_name,
            }
        else:
            resolved = value
            payload_body = {"address": step.address, "value": resolved}
        # Pre-effect in-flight marker (side-effecting step): record intent
        # BEFORE the write so a halt mid-write leaves a marker-without-outcome
        # the resume reader can identify. See `_RESULT_IN_FLIGHT`.
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_SETPOINT,
            body=payload_body,
            result=_RESULT_IN_FLIGHT,
        )
        try:
            await port.write(step.address, resolved, wait=True)
        except _CONTROL_ERRORS as exc:
            await self._record(
                envelope=envelope,
                index=index,
                step_kind=_STEP_KIND_SETPOINT,
                body=payload_body,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                source_kind=_STEP_KIND_SETPOINT,
                target=step.address,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        if step.verify:
            payload_body = {
                **payload_body,
                **(await self._post_read_evidence(step.address, port=port)),
            }
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_SETPOINT,
            body=payload_body,
            result=_RESULT_OK,
        )
        return None

    async def _post_read_evidence(self, address: str, *, port: ControlPort) -> dict[str, Any]:
        """Best-effort post-write `ControlPort.read` for the verify flag.

        Returns a dict with either `post_reading` (success) or
        `post_read_error` (Control*Error) for inclusion in the
        setpoint payload. Never raises; the write already succeeded
        and evidence capture is observational.
        """
        try:
            reading = await port.read(address)
        except _CONTROL_ERRORS as exc:
            return {
                "post_read_error": {
                    "error_class": type(exc).__name__,
                    "message": str(exc),
                }
            }
        return {"post_reading": _measurement_to_dict(reading)}

    async def _run_action(
        self,
        step: ActionStep,
        *,
        index: int,
        envelope: "_Envelope",
        port: ControlPort,
    ) -> ConductorFailure | None:
        payload_body: dict[str, Any] = {"name": step.name, "params": dict(step.params)}
        # Pre-effect in-flight marker (side-effecting step): record intent
        # BEFORE the action body runs so a halt mid-action leaves a
        # marker-without-outcome the resume reader can identify. An unknown
        # action still records the marker (the step kind is side-effecting)
        # then its failure outcome. See `_RESULT_IN_FLIGHT`.
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_ACTION,
            body=payload_body,
            result=_RESULT_IN_FLIGHT,
        )
        body = self._action_registry.lookup(step.name)
        if body is None:
            exc = UnknownActionError(step.name)
            await self._record(
                envelope=envelope,
                index=index,
                step_kind=_STEP_KIND_ACTION,
                body=payload_body,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                source_kind=_STEP_KIND_ACTION,
                target=step.name,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        try:
            result_data = await body(
                ActionContext(
                    control_port=port,
                    clock=self._clock,
                    params=step.params,
                )
            )
        except _CONTROL_ERRORS as exc:
            await self._record(
                envelope=envelope,
                index=index,
                step_kind=_STEP_KIND_ACTION,
                body=payload_body,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                source_kind=_STEP_KIND_ACTION,
                target=step.name,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_ACTION,
            body={**payload_body, "result_data": dict(result_data)},
            result=_RESULT_OK,
        )
        return None

    async def _run_check(
        self,
        step: CheckStep,
        *,
        index: int,
        envelope: "_Envelope",
        port: ControlPort,
    ) -> ConductorFailure | None:
        payload_body: dict[str, Any] = {
            "address": step.address,
            "criterion": _criterion_to_dict(step.criterion),
        }
        try:
            reading = await port.read(step.address)
        except _CONTROL_ERRORS as exc:
            await self._record(
                envelope=envelope,
                index=index,
                step_kind=_STEP_KIND_CHECK,
                body=payload_body,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                source_kind=_STEP_KIND_CHECK,
                target=step.address,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        body_with_reading = {**payload_body, "reading": _measurement_to_dict(reading)}
        if reading.quality != _QUALITY_GOOD:
            exc = CheckFailedError(step.address, f"quality={reading.quality}")
            await self._record(
                envelope=envelope,
                index=index,
                step_kind=_STEP_KIND_CHECK,
                body=body_with_reading,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                source_kind=_STEP_KIND_CHECK,
                target=step.address,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        if not _criterion_matches(step.criterion, reading.value):
            reason = _mismatch_reason(step.criterion, reading.value)
            exc = CheckFailedError(step.address, reason)
            await self._record(
                envelope=envelope,
                index=index,
                step_kind=_STEP_KIND_CHECK,
                body=body_with_reading,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                source_kind=_STEP_KIND_CHECK,
                target=step.address,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_CHECK,
            body=body_with_reading,
            result=_RESULT_OK,
        )
        return None

    async def _run_capture(
        self,
        step: CaptureStep,
        *,
        index: int,
        envelope: "_Envelope",
        port: ControlPort,
        captures: dict[str, Any],
    ) -> ConductorFailure | None:
        # A capture is a READ (no in-flight marker: not side-effecting). It
        # OBSERVES the live value and stores it for a later CaptureRef. The
        # read must be Good-quality + finite-numeric to be a safe restore
        # target; re-capture into a filled name is rejected.
        payload_body: dict[str, Any] = {
            "address": step.address,
            "capture_name": step.capture_name,
        }
        if step.capture_name in captures:
            msg = (
                f"capture {step.capture_name!r} already captured in this conduct "
                "(re-capture rejected)"
            )
            await self._record(
                envelope=envelope,
                index=index,
                step_kind=_STEP_KIND_CAPTURE,
                body=payload_body,
                result=_RESULT_FAILED,
                error_class=_ERROR_DUPLICATE_CAPTURE,
                message=msg,
            )
            return ConductorFailure(
                step_index=index,
                source_kind=_STEP_KIND_CAPTURE,
                target=step.capture_name,
                error_class=_ERROR_DUPLICATE_CAPTURE,
                message=msg,
            )
        try:
            reading = await port.read(step.address)
        except _CONTROL_ERRORS as exc:
            await self._record(
                envelope=envelope,
                index=index,
                step_kind=_STEP_KIND_CAPTURE,
                body=payload_body,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                source_kind=_STEP_KIND_CAPTURE,
                target=step.address,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        body_with_reading = {**payload_body, "reading": _measurement_to_dict(reading)}
        if reading.quality != _QUALITY_GOOD:
            quality_exc = CheckFailedError(step.address, f"quality={reading.quality}")
            await self._record(
                envelope=envelope,
                index=index,
                step_kind=_STEP_KIND_CAPTURE,
                body=body_with_reading,
                result=_RESULT_FAILED,
                error_class=type(quality_exc).__name__,
                message=str(quality_exc),
            )
            return ConductorFailure(
                step_index=index,
                source_kind=_STEP_KIND_CAPTURE,
                target=step.address,
                error_class=type(quality_exc).__name__,
                message=str(quality_exc),
            )
        try:
            captured_value = _require_finite_number(reading.value, step.address)
        except _CONTROL_ERRORS as exc:
            await self._record(
                envelope=envelope,
                index=index,
                step_kind=_STEP_KIND_CAPTURE,
                body=body_with_reading,
                result=_RESULT_FAILED,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return ConductorFailure(
                step_index=index,
                source_kind=_STEP_KIND_CAPTURE,
                target=step.address,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        captures[step.capture_name] = captured_value
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_CAPTURE,
            body={**body_with_reading, "captured_value": captured_value},
            result=_RESULT_OK,
        )
        return None

    async def _run_compute(
        self,
        step: ComputeStep,
        *,
        index: int,
        envelope: "_Envelope",
        compute: "_ComputeAccumulator",
        captures: dict[str, Any],
        outputs: dict[str, ArtifactRef],
    ) -> ConductorFailure | None:
        # A ComputeStep is side-effecting (a job submission is non-idempotent
        # at the substrate), so it follows the setpoint / action in-flight-marker
        # contract: a pre-effect marker BEFORE submit, then the ok / failed
        # outcome after. submit -> await -> then ONE output arm by `output_uri`:
        # value arm (None) fetches measurements; file arm (set) fetches an
        # artifact ref. Both fold the substrate's declared kind into the conduct.
        # When `capture_name` is set (value arm only), the produced scalar is
        # then deposited into `captures` for a later CaptureRef / convergence read.
        # When `output_ref_name` is set (file arm only), the produced ArtifactRef
        # is deposited into `outputs` for a later OutputRef input to resolve.
        if self._compute_port is None:
            # A wiring bug, not a runtime outcome: a ComputeStep was dispatched
            # but no ComputePort was supplied. Loud, like conduct()'s missing
            # lifecycle-handler guard; do not record a step failure.
            msg = (
                "Conductor._run_compute requires a compute_port at __init__; a ComputeStep "
                "was dispatched but none was wired. Pass compute_port to wire_operation."
            )
            raise RuntimeError(msg)
        port = self._compute_port
        # Resolve every OutputRef input against the per-conduct `outputs` bus
        # BEFORE any effect (parity with _run_setpoint's CaptureRef resolve): a
        # ref to a name never deposited loud-fails with a recorded entry, NO
        # in-flight marker, nothing submitted. The result is tuple[str, ...] so
        # the JobSpec + payload + ComputePort never see a ref. The pre-resolution
        # refs are recorded separately under `input_refs` for provenance.
        resolved_input_uris: list[str] = []
        for element_index, element in enumerate(step.input_uris):
            if isinstance(element, OutputRef):
                if element.output_name not in outputs:
                    msg = (
                        f"compute step input element {element_index} references output "
                        f"{element.output_name!r} not produced before this step "
                        f"(deposited: {sorted(outputs)})"
                    )
                    await self._record(
                        envelope=envelope,
                        index=index,
                        step_kind=_STEP_KIND_COMPUTE,
                        body={
                            "command": list(step.command),
                            "input_refs": [_input_uri_to_wire(u) for u in step.input_uris],
                            "output_uri": step.output_uri,
                            "parameters": dict(step.parameters),
                        },
                        result=_RESULT_FAILED,
                        error_class=_ERROR_UNRESOLVED_OUTPUT,
                        message=msg,
                    )
                    return ConductorFailure(
                        step_index=index,
                        source_kind=_STEP_KIND_COMPUTE,
                        target=" ".join(step.command),
                        error_class=_ERROR_UNRESOLVED_OUTPUT,
                        message=msg,
                    )
                resolved_input_uris.append(outputs[element.output_name].uri)
            else:
                resolved_input_uris.append(element)
        resolved_uris = tuple(resolved_input_uris)
        job_spec = JobSpec(
            command=step.command,
            input_uris=resolved_uris,
            output_uri=step.output_uri,
            parameters=step.parameters,
        )
        payload_body: dict[str, Any] = {
            "command": list(step.command),
            "input_uris": list(resolved_uris),
            "output_uri": step.output_uri,
            "parameters": dict(step.parameters),
        }
        # Provenance: record the pre-resolution refs (sentinel dicts for any
        # OutputRef element) beside the resolved URIs only when the step carried
        # a ref, mirroring _run_setpoint recording value + capture_ref.
        if any(isinstance(element, OutputRef) for element in step.input_uris):
            payload_body["input_refs"] = [_input_uri_to_wire(u) for u in step.input_uris]
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_COMPUTE,
            body=payload_body,
            result=_RESULT_IN_FLIGHT,
        )
        try:
            job_id = await port.submit(job_spec)
        except _COMPUTE_ERRORS as exc:
            return await self._record_compute_failure(
                envelope=envelope, index=index, body=payload_body, exc=exc, target=payload_body
            )
        body_with_job = {**payload_body, "job_id": str(job_id)}
        try:
            status = await port.await_terminal_state(job_id)
        except _COMPUTE_ERRORS as exc:
            return await self._record_compute_failure(
                envelope=envelope, index=index, body=body_with_job, exc=exc, target=payload_body
            )
        if not status.is_success:
            exc = ComputeJobFailedError(job_id, f"terminal status {status.value}")
            return await self._record_compute_failure(
                envelope=envelope,
                index=index,
                body={**body_with_job, "status": status.value},
                exc=exc,
                target=payload_body,
            )
        # Discriminate the output arm by `output_uri`: a file-producing step
        # (output_uri set) fetches an ArtifactRef; a value-producing step
        # (output_uri None) fetches Measurements. The recon-floor step is
        # artifact-only.
        if step.output_uri is not None:
            return await self._run_compute_artifact_arm(
                step,
                port=port,
                job_id=job_id,
                status=status,
                envelope=envelope,
                index=index,
                body_with_job=body_with_job,
                payload_body=payload_body,
                compute=compute,
                outputs=outputs,
            )
        try:
            produced = await port.fetch_measurements(job_id)
        except _COMPUTE_ERRORS as exc:
            return await self._record_compute_failure(
                envelope=envelope,
                index=index,
                body={**body_with_job, "status": status.value},
                exc=exc,
                target=payload_body,
            )
        result = port.provide_result(job_id, status, measurements=produced)
        compute.measurements.extend(result.measurements)
        # Fold the compute substrate's declared kind into the conduct's aggregate
        # kind via merge_actuation_kinds (NOT through _ActuationObserver, which
        # only watches the ControlPort): a Simulated solver taints the conduct
        # exactly as a simulated control route does.
        compute.kind = merge_actuation_kinds(compute.kind, result.actuation_kind.value)
        recorded_body = {
            **body_with_job,
            "status": status.value,
            "measurements": [_compute_measurement_to_dict(m) for m in result.measurements],
        }
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_COMPUTE,
            body=recorded_body,
            result=_RESULT_OK,
        )
        if step.capture_name is not None:
            return await self._deposit_compute_capture(
                step.capture_name,
                index=index,
                envelope=envelope,
                produced=result.measurements,
                base_body=recorded_body,
                captures=captures,
            )
        return None

    async def _deposit_compute_capture(
        self,
        capture_name: str,
        *,
        index: int,
        envelope: "_Envelope",
        produced: tuple[Measurement, ...],
        base_body: dict[str, Any],
        captures: dict[str, Any],
    ) -> ConductorFailure | None:
        """Deposit the named produced `Measurement`'s value into `captures` (slice 6c).

        Runs only when the ComputeStep carries a `capture_name` and its job
        already succeeded (the OK outcome is recorded). SELECTs the single
        produced `Measurement` whose `name == capture_name` with five loud
        failures, each recording a SEPARATE failed step entry + returning a
        HALTing `ConductorFailure` (no first-wins, no silent skip):

          1. no Measurement carries the name (`_ERROR_MEASUREMENT_NOT_FOUND`,
             naming the wanted + the available names);
          2. more than one Measurement carries the name
             (`_ERROR_AMBIGUOUS_MEASUREMENT`);
          3. the selected Measurement is not Good quality (re-gated exactly
             like `_run_capture`, via `CheckFailedError`);
          4. the selected value is not a finite number
             (`_require_finite_number`, mapped to `ControlValueCoercionError`);
          5. the slot is already filled in this conduct
             (`_ERROR_DUPLICATE_CAPTURE`, mirroring `_run_capture` ~1702).

        On success writes `captures[capture_name] = value` and returns None.
        """
        matches = [m for m in produced if m.name == capture_name]
        if not matches:
            available = sorted(m.name for m in produced if m.name)
            msg = (
                f"compute step found no produced measurement named {capture_name!r} "
                f"to capture (available: {available})"
            )
            return await self._record_compute_capture_failure(
                capture_name,
                index=index,
                envelope=envelope,
                base_body=base_body,
                error_class=_ERROR_MEASUREMENT_NOT_FOUND,
                message=msg,
            )
        if len(matches) > 1:
            msg = (
                f"compute step produced {len(matches)} measurements named "
                f"{capture_name!r}; an ambiguous capture is rejected (no first-wins)"
            )
            return await self._record_compute_capture_failure(
                capture_name,
                index=index,
                envelope=envelope,
                base_body=base_body,
                error_class=_ERROR_AMBIGUOUS_MEASUREMENT,
                message=msg,
            )
        selected = matches[0]
        if selected.quality != _QUALITY_GOOD:
            quality_exc = CheckFailedError(capture_name, f"quality={selected.quality}")
            return await self._record_compute_capture_failure(
                capture_name,
                index=index,
                envelope=envelope,
                base_body=base_body,
                error_class=type(quality_exc).__name__,
                message=str(quality_exc),
            )
        try:
            value = _require_finite_number(selected.value, capture_name)
        except _CONTROL_ERRORS as exc:
            return await self._record_compute_capture_failure(
                capture_name,
                index=index,
                envelope=envelope,
                base_body=base_body,
                error_class=type(exc).__name__,
                message=str(exc),
            )
        if capture_name in captures:
            msg = (
                f"compute capture {capture_name!r} already captured in this conduct "
                "(re-capture rejected)"
            )
            return await self._record_compute_capture_failure(
                capture_name,
                index=index,
                envelope=envelope,
                base_body=base_body,
                error_class=_ERROR_DUPLICATE_CAPTURE,
                message=msg,
            )
        captures[capture_name] = value
        return None

    async def _record_compute_capture_failure(
        self,
        capture_name: str,
        *,
        index: int,
        envelope: "_Envelope",
        base_body: dict[str, Any],
        error_class: str,
        message: str,
    ) -> ConductorFailure:
        """Record a failed compute-capture deposit + return the matching ConductorFailure.

        The job itself already recorded its OK outcome; this records a
        SEPARATE compute step entry for the deposit failure (so the journal
        carries both the produced measurements and the deposit fault) and
        HALTS the conduct."""
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_COMPUTE,
            body={**base_body, "capture_name": capture_name},
            result=_RESULT_FAILED,
            error_class=error_class,
            message=message,
        )
        return ConductorFailure(
            step_index=index,
            source_kind=_STEP_KIND_COMPUTE,
            target=capture_name,
            error_class=error_class,
            message=message,
        )

    async def _run_compute_artifact_arm(
        self,
        step: ComputeStep,
        *,
        port: ComputePort,
        job_id: Any,
        status: Any,
        envelope: "_Envelope",
        index: int,
        body_with_job: dict[str, Any],
        payload_body: dict[str, Any],
        compute: "_ComputeAccumulator",
        outputs: dict[str, ArtifactRef],
    ) -> ConductorFailure | None:
        """The file output arm of a ComputeStep: fetch the artifact + record it.

        Mirrors the value arm: fetch the produced output (`fetch_artifact_ref`
        rather than `fetch_measurements`), assemble the `ComputeResult` so the
        adapter stamps the kind, fold that kind into the conduct, and record
        the ok outcome. The `ArtifactRef` is surfaced on
        `ConductorResult.artifacts` so the caller can register a Dataset
        against it. When the step carries an `output_ref_name`, after the OK
        record the produced `ArtifactRef` is deposited into the per-conduct
        `outputs` bus (loud-failing on an already-filled slot) so a later
        step's `OutputRef` input resolves to it.
        """
        try:
            artifact = await port.fetch_artifact_ref(job_id)
        except _COMPUTE_ERRORS as exc:
            return await self._record_compute_failure(
                envelope=envelope,
                index=index,
                body={**body_with_job, "status": status.value},
                exc=exc,
                target=payload_body,
            )
        result = port.provide_result(job_id, status, artifacts=(artifact,))
        compute.artifacts.extend(result.artifacts)
        compute.kind = merge_actuation_kinds(compute.kind, result.actuation_kind.value)
        recorded_body = {
            **body_with_job,
            "status": status.value,
            "artifacts": [_compute_artifact_to_dict(a) for a in result.artifacts],
        }
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_COMPUTE,
            body=recorded_body,
            result=_RESULT_OK,
        )
        if step.output_ref_name is not None:
            duplicate = self._deposit_compute_output(
                step.output_ref_name, artifact=artifact, outputs=outputs
            )
            if duplicate:
                return await self._record_compute_output_failure(
                    step.output_ref_name,
                    index=index,
                    envelope=envelope,
                    base_body=recorded_body,
                )
        return None

    def _deposit_compute_output(
        self,
        output_ref_name: str,
        *,
        artifact: ArtifactRef,
        outputs: dict[str, ArtifactRef],
    ) -> bool:
        """Deposit a file-arm `ArtifactRef` into `outputs[output_ref_name]`.

        The compute-branch twin of `_deposit_compute_capture`. The file arm
        fetches exactly ONE ArtifactRef, so the only loud-fail is a duplicate
        slot (no absent / ambiguous / quality / finite arms the value-arm
        deposit needs). Returns True when the slot was already filled (the
        caller records the `DuplicateOutput` failure + halts); on success
        writes the FULL `ArtifactRef` (keeping checksum / byte_size for a future
        upstream-integrity check) and returns False.
        """
        if output_ref_name in outputs:
            return True
        outputs[output_ref_name] = artifact
        return False

    async def _record_compute_output_failure(
        self,
        output_ref_name: str,
        *,
        index: int,
        envelope: "_Envelope",
        base_body: dict[str, Any],
    ) -> ConductorFailure:
        """Record a failed compute-output deposit (duplicate slot) + return the failure.

        The job already recorded its OK outcome; this records a SEPARATE compute
        step entry for the deposit fault (so the journal carries both the
        produced artifact and the duplicate-output fault) and HALTS the conduct.
        Mirrors `_record_compute_capture_failure`."""
        msg = (
            f"compute output {output_ref_name!r} already produced in this conduct "
            "(duplicate output rejected)"
        )
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_COMPUTE,
            body={**base_body, "output_ref_name": output_ref_name},
            result=_RESULT_FAILED,
            error_class=_ERROR_DUPLICATE_OUTPUT,
            message=msg,
        )
        return ConductorFailure(
            step_index=index,
            source_kind=_STEP_KIND_COMPUTE,
            target=output_ref_name,
            error_class=_ERROR_DUPLICATE_OUTPUT,
            message=msg,
        )

    async def _record_compute_failure(
        self,
        *,
        envelope: "_Envelope",
        index: int,
        body: dict[str, Any],
        exc: Exception,
        target: dict[str, Any],
    ) -> ConductorFailure:
        """Record a failed ComputeStep outcome + return the matching ConductorFailure.

        `target` carries the command summary so the failure's `target` reads
        the same whichever leg (submit / await / non-terminal / fetch) failed.
        """
        await self._record(
            envelope=envelope,
            index=index,
            step_kind=_STEP_KIND_COMPUTE,
            body=body,
            result=_RESULT_FAILED,
            error_class=type(exc).__name__,
            message=str(exc),
        )
        return ConductorFailure(
            step_index=index,
            source_kind=_STEP_KIND_COMPUTE,
            target=" ".join(target["command"]),
            error_class=type(exc).__name__,
            message=str(exc),
        )

    async def _record(
        self,
        *,
        envelope: "_Envelope",
        index: int,
        step_kind: str,
        body: dict[str, Any],
        result: str,
        error_class: str | None = None,
        message: str | None = None,
    ) -> None:
        """Append a single step entry via the injected handler.

        The payload merges the kind-specific `body` with the
        Conductor-local `result` discriminator (plus `error_class` +
        `message` on failure). Future iterations may extend the body
        shape (pre/post readings, retry counts, etc.) additively.

        `index` is the step's zero-based position in the conducted step
        list; it rides the payload as `step_index` so a future resume
        can map a recorded outcome back to its position in the pinned
        resolved step list.
        """
        payload: dict[str, Any] = {**body, "step_index": index, "result": result}
        if error_class is not None:
            payload["error_class"] = error_class
        if message is not None:
            payload["message"] = message
        sampled_at = self._clock.now()
        entry = ActivityInput(
            event_id=self._id_generator.new_id(),
            step_kind=step_kind,
            payload=payload,
            sampled_at=sampled_at,
            occurred_at=sampled_at,
        )
        await self._append_step(
            AppendProcedureActivities(procedure_id=envelope.procedure_id, entries=(entry,)),
            principal_id=envelope.principal_id,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            surface_id=envelope.surface_id,
        )


@dataclass(frozen=True)
class _Envelope:
    """Bag of per-execute envelope fields the Conductor threads to `_record`.

    Internal helper; avoids passing six args to every helper method.
    Frozen so accidental mutation mid-execute is a type error.
    """

    procedure_id: UUID
    principal_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    surface_id: UUID


@dataclass
class _ComputeAccumulator:
    """Per-conduct compute output accumulator threaded through `_dispatch`.

    A `ComputeStep` appends its produced `Measurement`s to `measurements`
    (the value arm) or its `ArtifactRef`s to `artifacts` (the file arm),
    both surfaced on `ConductorResult`, and folds its declared
    `ActuationKind` into `kind` via `merge_actuation_kinds`, so a simulated
    solver taints the conduct's aggregate kind. Mutable (not frozen): the
    dispatch loop accumulates into it across steps. `kind` is the raw
    `ActuationKind` string value or None (no ComputeStep ran).
    """

    measurements: list[Measurement] = field(default_factory=list[Measurement])
    artifacts: list[ArtifactRef] = field(default_factory=list[ArtifactRef])
    kind: str | None = None


def _fold_compute_kind(
    observed: ActuationKind | None, compute_kind: str | None
) -> ActuationKind | None:
    """Merge the ControlPort-observed kind with the ComputeStep-folded kind.

    The control-side kind comes from `_ActuationObserver`; the compute-side
    kind is folded separately (the observer never watches ComputePort). When
    no ComputeStep ran, `compute_kind` is None and the observed kind passes
    through unchanged. Returns the honest aggregate `ActuationKind` (or None
    when neither side observed anything)."""
    if compute_kind is None:
        return observed
    merged = merge_actuation_kinds(observed.value if observed is not None else None, compute_kind)
    return ActuationKind(merged) if merged is not None else None


def _criterion_to_dict(criterion: CheckCriterion) -> dict[str, Any]:
    """Serialize a criterion into a JSON-clean dict for the step payload."""
    if isinstance(criterion, EqualsCriterion):
        return {"kind": "equals", "expected": criterion.expected}
    return {
        "kind": "within_tolerance",
        "expected": criterion.expected,
        "tolerance": criterion.tolerance,
    }


def step_to_payload(step: Step) -> dict[str, Any]:
    """Serialize a `Step` to a JSON-clean dict (inverse of `steps_from_payload`).

    Mirrors the conduct route's wire shape (the `kind` discriminator +
    field names) so the resolved step list pinned on `ResolvedStepsRecorded`
    round-trips back to `Step` objects via `steps_from_payload` at resume
    (and via the route's Pydantic `step_from_wire` on the live HTTP path). A
    tuple `value` serializes as a list (JSON has no tuple); the criterion
    reuses `_criterion_to_dict` so the wire shape stays single-sourced.
    """
    if isinstance(step, SetpointStep):
        if isinstance(step.value, CaptureRef):
            value: Any = {_CAPTURE_REF_KEY: step.value.capture_name}
        elif isinstance(step.value, tuple):
            value = list(step.value)
        else:
            value = step.value
        return {
            "kind": "setpoint",
            "address": step.address,
            "value": value,
            "verify": step.verify,
        }
    if isinstance(step, ActionStep):
        return {"kind": "action", "name": step.name, "params": dict(step.params)}
    if isinstance(step, CaptureStep):
        return {
            "kind": "capture",
            "address": step.address,
            "capture_name": step.capture_name,
        }
    if isinstance(step, ComputeStep):
        return {
            "kind": "compute",
            "command": list(step.command),
            "input_uris": [_input_uri_to_wire(u) for u in step.input_uris],
            "output_uri": step.output_uri,
            "parameters": dict(step.parameters),
            "capture_name": step.capture_name,
            "output_ref_name": step.output_ref_name,
        }
    return {
        "kind": "check",
        "address": step.address,
        "criterion": _criterion_to_dict(step.criterion),
    }


def _criterion_from_dict(criterion: Mapping[str, Any]) -> CheckCriterion:
    """Rebuild a `CheckCriterion` from its `_criterion_to_dict` shape."""
    kind = criterion["kind"]
    if kind == "equals":
        expected: Any = criterion["expected"]
        if isinstance(expected, list):
            expected = cast("tuple[Any, ...]", tuple(expected))  # pyright: ignore[reportUnknownArgumentType]
        return EqualsCriterion(expected=expected)
    if kind == "within_tolerance":
        return WithinToleranceCriterion(
            expected=criterion["expected"], tolerance=criterion["tolerance"]
        )
    msg = f"unknown criterion kind: {kind!r}"
    raise ValueError(msg)


def _step_from_payload(payload: Mapping[str, Any]) -> Step:
    """Rebuild one `Step` from its `step_to_payload` wire shape."""
    kind = payload["kind"]
    if kind == "setpoint":
        raw: Any = payload["value"]
        value: int | float | bool | str | tuple[Any, ...] | CaptureRef
        if isinstance(raw, dict) and set(cast("dict[str, Any]", raw)) == {_CAPTURE_REF_KEY}:
            value = CaptureRef(capture_name=str(cast("dict[str, Any]", raw)[_CAPTURE_REF_KEY]))
        elif isinstance(raw, list):
            value = tuple(cast("list[Any]", raw))
        else:
            value = cast("int | float | bool | str", raw)
        return SetpointStep(
            address=payload["address"], value=value, verify=payload.get("verify", False)
        )
    if kind == "action":
        return ActionStep(name=payload["name"], params=dict(payload.get("params", {})))
    if kind == "capture":
        return CaptureStep(address=payload["address"], capture_name=payload["capture_name"])
    if kind == "compute":
        return ComputeStep(
            command=tuple(payload["command"]),
            input_uris=tuple(_input_uri_from_wire(u) for u in payload.get("input_uris", ())),
            output_uri=payload.get("output_uri"),
            parameters=dict(payload.get("parameters", {})),
            capture_name=payload.get("capture_name"),
            output_ref_name=payload.get("output_ref_name"),
        )
    if kind == "check":
        return CheckStep(
            address=payload["address"], criterion=_criterion_from_dict(payload["criterion"])
        )
    msg = f"unknown step kind: {kind!r}"
    raise ValueError(msg)


def steps_from_payload(resolved_steps: Sequence[Mapping[str, Any]]) -> tuple[Step, ...]:
    """Parse the pinned `ResolvedStepsRecorded.resolved_steps` back into `Step`s.

    The exact inverse of `step_to_payload` (the serialization used to pin the
    resolved step list). A resume reads the pinned event's `resolved_steps`,
    parses them with this helper, and hands the result to
    `Conductor.execute_from` -- it NEVER re-derives the step list from live
    `Plan.wires` / partition rules. Pure; no Pydantic (that lives at the HTTP
    boundary in `step_from_wire`). See [[project_resumable_conduct_design]].
    """
    return tuple(_step_from_payload(step) for step in resolved_steps)


def is_acquisition_halt(failure: ConductorFailure | None) -> bool:
    """True iff `failure` is `execute_from`'s halt-for-operator on an acquisition.

    Distinguishes the resume halt (an `ActionStep` reached during replay,
    which is a needs-operator-decision hand-off, NOT a failure) from a
    genuine step failure (a setpoint/check that failed). A resume
    orchestration completes on success, leaves the Procedure Running on an
    acquisition halt, and aborts on a genuine failure -- this predicate is
    the branch. See `_RESUME_HALT_ERROR_CLASS` and
    [[project_resumable_conduct_design]]."""
    return failure is not None and failure.error_class == _RESUME_HALT_ERROR_CLASS


def _is_recoverable_failure(failure: ConductorFailure) -> bool:
    """True iff a conduct step failure is safe to PAUSE-and-resume, not abort.

    Recoverable = a setpoint or check failure: on `reconduct` a setpoint is
    re-driven (idempotent absolute write) and a check is re-run as a fresh
    gate, so the conduct can honestly continue from the boundary. An action
    failure is NOT recoverable here: an interrupted acquisition is
    non-idempotent (Tier 2 per-point decomposition is the real fix), and a
    Held Procedure whose replay tail starts with that acquisition could only
    halt-for-operator on `reconduct`. This is `try_conduct`'s hold-vs-abort
    branch; lifecycle failures never reach it (handled before the step-failure
    branch). See [[project_resumable_conduct_design]] Tier 1."""
    return failure.source_kind in (_STEP_KIND_SETPOINT, _STEP_KIND_CHECK)


def _criterion_matches(criterion: CheckCriterion, value: Any) -> bool:
    """True iff `value` satisfies `criterion`.

    `WithinToleranceCriterion` tolerates non-numeric values: a `TypeError` or
    `ValueError` from `float(value)` is treated as a clean mismatch
    rather than escaping. This is the right shape because a reading
    that isn't numerically comparable IS a failed check, not a bug.
    """
    if isinstance(criterion, EqualsCriterion):
        return value == criterion.expected
    try:
        return abs(float(value) - criterion.expected) <= criterion.tolerance
    except (TypeError, ValueError):
        return False


def _mismatch_reason(criterion: CheckCriterion, value: Any) -> str:
    """Operator-friendly explanation for a failed criterion."""
    if isinstance(criterion, EqualsCriterion):
        return f"value {value!r} did not equal expected {criterion.expected!r}"
    return f"value {value!r} not within {criterion.tolerance} of expected {criterion.expected}"


def _derive_failure_reason(failure: ConductorFailure) -> str:
    """Build a Procedure-aggregate-compliant reason string from a step failure.

    Used for both the abort path (`conduct` / `reconduct`) and the
    pause-to-Held path (`try_conduct`). Truncates to `REASON_MAX_LENGTH` so
    the AbortProcedure / HoldProcedure handler does not reject the call. The
    format leads with the step pointer (kind + index + target) so an operator
    scanning the reason knows immediately which step in the conducted sequence
    halted the Procedure.
    """
    if failure.step_index is None:
        prefix = f"{failure.source_kind} {failure.target}"
    else:
        prefix = f"{failure.source_kind}[{failure.step_index}] {failure.target}"
    reason = f"{prefix} failed: {failure.error_class}: {failure.message}"
    return reason[:REASON_MAX_LENGTH]


def _measurement_to_dict(reading: Measurement) -> dict[str, Any]:
    """JSON-clean projection of `Measurement` for the step payload.

    Includes the substrate metadata fields a post-hoc inspector needs
    (quality + quality_detail + ISO-8601 produced_at) so a check entry
    is self-contained without joining back to a separate stream.
    """
    return {
        "value": reading.value,
        "kind": reading.kind,
        "quality": reading.quality,
        "quality_detail": reading.quality_detail,
        "sampled_at": reading.produced_at.isoformat(),
    }


def _compute_measurement_to_dict(measurement: Measurement) -> dict[str, Any]:
    """JSON-clean projection of a ComputeStep `Measurement` for the step payload.

    SEPARATE from `_measurement_to_dict` (the control / check / capture
    flattener) on purpose: that one's key set is pinned by the
    projection-metadata frozenset tests and must NOT widen. A compute
    Measurement names a quantity (`name`) and carries `units`, both
    load-bearing for the Calibration write the scenario does off the
    surfaced value, so this flattener keeps them while the control one
    drops them (a control reading is identified by address, not name).
    """
    return {
        "name": measurement.name,
        "value": measurement.value,
        "kind": measurement.kind,
        "units": measurement.units,
        "quality": measurement.quality,
    }


def _compute_artifact_to_dict(artifact: ArtifactRef) -> dict[str, Any]:
    """JSON-clean projection of a file-arm ComputeStep `ArtifactRef`.

    The file-arm sibling of `_compute_measurement_to_dict`. Records the
    reference's identifying + verification fields on the step payload so
    log inspection from the read side sees what the job wrote without
    re-statting the file. `conforms_to` is a tuple; serialize as a list.
    """
    return {
        "uri": artifact.uri,
        "checksum_algorithm": artifact.checksum_algorithm,
        "checksum_value": artifact.checksum_value,
        "byte_size": artifact.byte_size,
        "media_type": artifact.media_type,
        "conforms_to": list(artifact.conforms_to),
        "entry_count": artifact.entry_count,
    }


__all__ = [
    "ActionBody",
    "ActionContext",
    "ActionRegistry",
    "ActionStep",
    "CaptureStep",
    "CheckCriterion",
    "CheckStep",
    "ComputeStep",
    "Conductor",
    "ConductorFailure",
    "ConductorResult",
    "EqualsCriterion",
    "InMemoryActionRegistry",
    "ResumePolicy",
    "SetpointStep",
    "Step",
    "WithinToleranceCriterion",
    "is_acquisition_halt",
    "step_to_payload",
    "steps_from_payload",
]
