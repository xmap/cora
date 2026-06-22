"""Operation BC `Conductor`: walks Procedure steps via ControlPort + actions + checks.

The Conductor is the Operation BC's Layer-2 runtime per
[[project_edge_runtime_design]]. It receives a sequence of `Step`
operations (a discriminated union over `SetpointStep | ActionStep |
CheckStep`), dispatches each through the right primitive
(`ControlPort.write` for setpoints, an action body looked up in the
`ActionRegistry` for actions, `ControlPort.read` followed by
criterion evaluation for checks), and records every outcome as a
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
`Reading.quality == "Good"` (Uncertain or Bad fails the check), and
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

import asyncio
import contextlib
import math
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Protocol, cast
from uuid import UUID

from cora.infrastructure.ports.clock import Clock
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.ports.id_generator import IdGenerator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._control_dispatch_context import with_dispatch_correlation_id
from cora.operation.aggregates.procedure import ProcedureNotFoundError, merge_actuation_kinds
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
from cora.operation.features.hold_procedure.command import HoldProcedure
from cora.operation.features.hold_procedure.handler import Handler as HoldProcedureHandler
from cora.operation.features.resume_procedure.command import ResumeProcedure
from cora.operation.features.resume_procedure.handler import Handler as ResumeProcedureHandler
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.features.start_procedure.handler import Handler as StartProcedureHandler
from cora.operation.ports.control_port import (
    ActuationKind,
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlPort,
    ControlTimeoutError,
    ControlValueCoercionError,
    ControlWriteRejectedError,
    NoAdapterForAddressError,
    Reading,
)
from cora.recipe.aggregates.recipe.body import CaptureRef
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

_ERROR_UNRESOLVED_CAPTURE = "UnresolvedCaptureRef"
"""error_class for a SetpointStep CaptureRef whose name was never captured
in this conduct (e.g. resumed past the capturing step). Loud-fail label,
not an exception type: the failure is recorded + returned, not raised."""

_ERROR_DUPLICATE_CAPTURE = "DuplicateCapture"
"""error_class for a CaptureStep re-capturing an already-filled name within
one conduct (an authoring error the recipe validation also rejects)."""

_CAPTURE_REF_KEY = "__capture__"
"""Wire-format sentinel key for a `CaptureRef` value in the pinned conduct
step payload (mirrors the Recipe BC's `__capture__` form). A `SetpointStep`
whose value is a `CaptureRef` serializes to `{"__capture__": name}` so it
rides `ResolvedStepsRecorded` + the determinism hash as an opaque sentinel
and round-trips at resume; the Conductor resolves it at execute time."""
"""Closed-set discriminator from [[project_operation_design]]
(`setpoint | action | check`). Source of truth for these values is
`STEP_KIND_VALUES` on the Procedure aggregate (re-imported above);
the architecture fitness `test_conductor_step_kinds_match_procedure`
pins that the union arms here stay in sync with the aggregate set.

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
    `Reading.quality == "Good"`, then evaluates `criterion` against
    `Reading.value`. Any of (read raised `Control*Error`, quality
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


Step = SetpointStep | ActionStep | CheckStep | CaptureStep
"""The closed discriminated union of step kinds the Conductor walks.

Mirrors the open `StepKind` Literal in the Procedure aggregate
(`"setpoint" | "action" | "check" | "capture"`); the Conductor enforces
tighter typing via this union so a malformed step is a type error, not a
runtime branch."""


def _require_finite_number(value: Any, address: str) -> float:
    """Return `value` as a finite number or raise a Conductor-recordable failure.

    A captured axis read feeds a later restore setpoint, so it must be a
    finite number. `Reading.value` is typed `Any`; a non-numeric read (a
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
    """

    procedure_id: UUID
    completed_count: int
    failure: ConductorFailure | None = None
    actuation_kind: ActuationKind | None = None
    held: bool = False

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

    async def read(self, address: str) -> Reading:
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

    def subscribe(self, address: str) -> AsyncIterator[Reading]:
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
        start_procedure: StartProcedureHandler | None = None,
        complete_procedure: CompleteProcedureHandler | None = None,
        abort_procedure: AbortProcedureHandler | None = None,
        resume_procedure: ResumeProcedureHandler | None = None,
        hold_procedure: HoldProcedureHandler | None = None,
    ) -> None:
        self._control_port = control_port
        self._append_step = append_step
        self._clock = clock
        self._id_generator = id_generator
        self._action_registry: ActionRegistry = action_registry or InMemoryActionRegistry({})
        self._start_procedure = start_procedure
        self._complete_procedure = complete_procedure
        self._abort_procedure = abort_procedure
        self._resume_procedure = resume_procedure
        self._hold_procedure = hold_procedure

    async def execute(
        self,
        *,
        procedure_id: UUID,
        principal_id: UUID,
        correlation_id: UUID,
        steps: Sequence[Step],
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
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
        """
        envelope = _Envelope(
            procedure_id=procedure_id,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )
        observer = _ActuationObserver(self._control_port)
        captures: dict[str, Any] = {}
        completed = 0
        for index, step in enumerate(steps):
            # Bind correlation_id to the ContextVar scoped per dispatch so
            # ControlPort adapters can emit `controlport.dispatch` events
            # without taking a kwarg. See `_control_dispatch_context` for
            # the why; contextvars survive each `await` inside `_dispatch`
            # and reset cleanly on exception.
            with with_dispatch_correlation_id(correlation_id):
                failure = await self._dispatch(
                    step, index=index, envelope=envelope, port=observer, captures=captures
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
        try:
            result = await self.execute(
                procedure_id=procedure_id,
                principal_id=principal_id,
                correlation_id=correlation_id,
                steps=steps,
                causation_id=causation_id,
                surface_id=surface_id,
            )
        except asyncio.CancelledError:
            # The execute() call was cancelled mid-flight (caller cancelled
            # the conducting task or the loop is shutting down). The
            # Procedure is now in `Running` with partial step history; if
            # we let the cancellation propagate untouched, the FSM would
            # be orphaned. Best-effort transition to Aborted so operator
            # state reflects what happened. Re-raise so the caller's task
            # still sees the cancellation - this keeps signals + shutdown
            # behaving normally.
            with contextlib.suppress(Exception):
                # No ConductorResult is available on cancellation (execute()
                # raised before returning), so the observed actuation kind is
                # unrecoverable here: abort records None. Conservative residual
                # documented in the activation design; a Dataset off a
                # cancelled conduct carries no proven kind.
                await self._abort_procedure(
                    AbortProcedure(procedure_id=procedure_id, reason="cancelled mid-execute"),
                    **envelope_kwargs,
                )
            raise
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
        try:
            result = await self.execute(
                procedure_id=procedure_id,
                principal_id=principal_id,
                correlation_id=correlation_id,
                steps=steps,
                causation_id=causation_id,
                surface_id=surface_id,
            )
        except asyncio.CancelledError:
            # Mirror conduct(): best-effort abort so the FSM is not orphaned in
            # Running, then re-raise. A cancellation is not a recoverable step
            # failure, so it aborts rather than pausing to Held.
            with contextlib.suppress(Exception):
                await self._abort_procedure(
                    AbortProcedure(procedure_id=procedure_id, reason="cancelled mid-execute"),
                    **envelope_kwargs,
                )
            raise
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
    ) -> ConductorFailure | None:
        """Run one step + record outcome; return ConductorFailure on halt-condition.

        `port` is the per-conduct observing wrapper around the
        Conductor's ControlPort; every dispatch goes through it so
        actuation provenance is captured once for the whole conduct.
        `captures` is the per-conduct slot dict: a `CaptureStep` fills it,
        a `SetpointStep` with a `CaptureRef` value reads it.
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
        return {"post_reading": _reading_to_dict(reading)}

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
        body_with_reading = {**payload_body, "reading": _reading_to_dict(reading)}
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
        body_with_reading = {**payload_body, "reading": _reading_to_dict(reading)}
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


def _reading_to_dict(reading: Reading) -> dict[str, Any]:
    """JSON-clean projection of `Reading` for the step payload.

    Includes the substrate metadata fields a post-hoc inspector needs
    (quality + quality_detail + ISO-8601 sampled_at) so a check entry
    is self-contained without joining back to a separate stream.
    """
    return {
        "value": reading.value,
        "kind": reading.kind,
        "quality": reading.quality,
        "quality_detail": reading.quality_detail,
        "sampled_at": reading.sampled_at.isoformat(),
    }


__all__ = [
    "ActionBody",
    "ActionContext",
    "ActionRegistry",
    "ActionStep",
    "CaptureStep",
    "CheckCriterion",
    "CheckStep",
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
