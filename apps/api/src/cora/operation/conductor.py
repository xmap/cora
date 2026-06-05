"""Operation BC `Conductor`: walks Procedure steps via ControlPort + actions + checks.

The Conductor is the Operation BC's Layer-2 runtime per
[[project_edge_runtime_design]]. It receives a sequence of `Step`
operations (a discriminated union over `SetpointStep | ActionStep |
CheckStep`), dispatches each through the right primitive
(`ControlPort.write` for setpoints, an action body looked up in the
`ActionRegistry` for actions, `ControlPort.read` followed by
criterion evaluation for checks), and records every outcome as a
step entry in the Procedure's steps logbook via the existing
`append_procedure_steps` handler.

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

`append_procedure_steps` is the slice handler that owns lazy-open of
the steps logbook + status guard (Procedure must be `Running`) +
authorization. The Conductor calls the handler, not the underlying
`StepStore`, so those concerns stay caged inside the existing slice
and the Conductor stays a thin orchestrator. The dependency is the
handler's `Handler` Protocol, not a concrete binding, so tests inject
a fake without standing up the full handler machinery.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.ports.clock import Clock
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.ports.id_generator import IdGenerator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._control_dispatch_context import with_dispatch_correlation_id
from cora.operation.aggregates.procedure import (
    PROCEDURE_ABORT_REASON_MAX_LENGTH,
    ProcedureNotFoundError,
)
from cora.operation.errors import CheckFailedError, UnauthorizedError, UnknownActionError
from cora.operation.features.abort_procedure.command import AbortProcedure
from cora.operation.features.abort_procedure.handler import Handler as AbortProcedureHandler
from cora.operation.features.append_procedure_steps.command import (
    AppendProcedureSteps,
    ProcedureStepInput,
)
from cora.operation.features.append_procedure_steps.handler import (
    Handler as AppendProcedureStepsHandler,
)
from cora.operation.features.complete_procedure.command import CompleteProcedure
from cora.operation.features.complete_procedure.handler import (
    Handler as CompleteProcedureHandler,
)
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.features.start_procedure.handler import Handler as StartProcedureHandler
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlPort,
    ControlTimeoutError,
    ControlValueCoercionError,
    ControlWriteRejectedError,
    NoAdapterForAddressError,
    Reading,
)

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
ProcedureStep entry; the failure surfaces only on the result."""

_LIFECYCLE_TARGET_START = "start"
_LIFECYCLE_TARGET_COMPLETE = "complete"
_LIFECYCLE_TARGET_ABORT = "abort"

_RESULT_OK = "ok"
_RESULT_FAILED = "failed"
"""Conductor-local convention inside the step payload body; today's
projections do not split on it, but the field is pinned so future
read-side filters can separate successful vs failed steps without
parsing the message string."""

_QUALITY_GOOD = "Good"


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
    """

    address: str
    value: int | float | bool | str | tuple[Any, ...]
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


Step = SetpointStep | ActionStep | CheckStep
"""The closed discriminated union of step kinds the Conductor walks.

Mirrors the open `StepKind` Literal in the Procedure aggregate
(`"setpoint" | "action" | "check"`); the Conductor enforces tighter
typing via this union so a malformed step is a type error, not a
runtime branch."""


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
    """

    procedure_id: UUID
    completed_count: int
    failure: ConductorFailure | None = None

    @property
    def succeeded(self) -> bool:
        return self.failure is None


class Conductor:
    """Operation BC Layer-2 runtime: walks `Step`s via ControlPort + action registry.

    Stateless walker. Construct once at app wire-up time; call
    `execute` per Procedure execution. Per-call state lives on the
    returned `ConductorResult`.

    The Conductor calls the `append_procedure_steps` handler (not the
    underlying `StepStore`) so lazy-open + status guard + authorization
    stay inside that slice. See module docstring for failure mode +
    out-of-scope.
    """

    def __init__(
        self,
        *,
        control_port: ControlPort,
        append_step: AppendProcedureStepsHandler,
        clock: Clock,
        id_generator: IdGenerator,
        action_registry: ActionRegistry | None = None,
        start_procedure: StartProcedureHandler | None = None,
        complete_procedure: CompleteProcedureHandler | None = None,
        abort_procedure: AbortProcedureHandler | None = None,
    ) -> None:
        self._control_port = control_port
        self._append_step = append_step
        self._clock = clock
        self._id_generator = id_generator
        self._action_registry: ActionRegistry = action_registry or InMemoryActionRegistry({})
        self._start_procedure = start_procedure
        self._complete_procedure = complete_procedure
        self._abort_procedure = abort_procedure

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
        completed = 0
        for index, step in enumerate(steps):
            # Bind correlation_id to the ContextVar scoped per dispatch so
            # ControlPort adapters can emit `controlport.dispatch` events
            # without taking a kwarg. See `_control_dispatch_context` for
            # the why; contextvars survive each `await` inside `_dispatch`
            # and reset cleanly on exception.
            with with_dispatch_correlation_id(correlation_id):
                failure = await self._dispatch(step, index=index, envelope=envelope)
            if failure is not None:
                return ConductorResult(
                    procedure_id=procedure_id,
                    completed_count=completed,
                    failure=failure,
                )
            completed += 1
        return ConductorResult(procedure_id=procedure_id, completed_count=completed)

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
                await self._abort_procedure(
                    AbortProcedure(procedure_id=procedure_id, reason="cancelled mid-execute"),
                    **envelope_kwargs,
                )
            raise
        if result.succeeded:
            try:
                await self._complete_procedure(
                    CompleteProcedure(procedure_id=procedure_id), **envelope_kwargs
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
        reason = _derive_abort_reason(failure)
        with contextlib.suppress(Exception):
            await self._abort_procedure(
                AbortProcedure(procedure_id=procedure_id, reason=reason),
                **envelope_kwargs,
            )
        return result

    async def _dispatch(
        self,
        step: Step,
        *,
        index: int,
        envelope: "_Envelope",
    ) -> ConductorFailure | None:
        """Run one step + record outcome; return ConductorFailure on halt-condition."""
        if isinstance(step, SetpointStep):
            return await self._run_setpoint(step, index=index, envelope=envelope)
        if isinstance(step, ActionStep):
            return await self._run_action(step, index=index, envelope=envelope)
        return await self._run_check(step, index=index, envelope=envelope)

    async def _run_setpoint(
        self,
        step: SetpointStep,
        *,
        index: int,
        envelope: "_Envelope",
    ) -> ConductorFailure | None:
        payload_body: dict[str, Any] = {"address": step.address, "value": step.value}
        try:
            await self._control_port.write(step.address, step.value, wait=True)
        except _CONTROL_ERRORS as exc:
            await self._record(
                envelope=envelope,
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
            payload_body = {**payload_body, **(await self._post_read_evidence(step.address))}
        await self._record(
            envelope=envelope,
            step_kind=_STEP_KIND_SETPOINT,
            body=payload_body,
            result=_RESULT_OK,
        )
        return None

    async def _post_read_evidence(self, address: str) -> dict[str, Any]:
        """Best-effort post-write `ControlPort.read` for the verify flag.

        Returns a dict with either `post_reading` (success) or
        `post_read_error` (Control*Error) for inclusion in the
        setpoint payload. Never raises; the write already succeeded
        and evidence capture is observational.
        """
        try:
            reading = await self._control_port.read(address)
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
    ) -> ConductorFailure | None:
        payload_body: dict[str, Any] = {"name": step.name, "params": dict(step.params)}
        body = self._action_registry.lookup(step.name)
        if body is None:
            exc = UnknownActionError(step.name)
            await self._record(
                envelope=envelope,
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
                    control_port=self._control_port,
                    clock=self._clock,
                    params=step.params,
                )
            )
        except _CONTROL_ERRORS as exc:
            await self._record(
                envelope=envelope,
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
    ) -> ConductorFailure | None:
        payload_body: dict[str, Any] = {
            "address": step.address,
            "criterion": _criterion_to_dict(step.criterion),
        }
        try:
            reading = await self._control_port.read(step.address)
        except _CONTROL_ERRORS as exc:
            await self._record(
                envelope=envelope,
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
            step_kind=_STEP_KIND_CHECK,
            body=body_with_reading,
            result=_RESULT_OK,
        )
        return None

    async def _record(
        self,
        *,
        envelope: "_Envelope",
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
        """
        payload: dict[str, Any] = {**body, "result": result}
        if error_class is not None:
            payload["error_class"] = error_class
        if message is not None:
            payload["message"] = message
        sampled_at = self._clock.now()
        entry = ProcedureStepInput(
            event_id=self._id_generator.new_id(),
            step_kind=step_kind,
            payload=payload,
            sampled_at=sampled_at,
            occurred_at=sampled_at,
        )
        await self._append_step(
            AppendProcedureSteps(procedure_id=envelope.procedure_id, entries=(entry,)),
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


def _derive_abort_reason(failure: ConductorFailure) -> str:
    """Build a Procedure-aggregate-compliant abort reason from a step failure.

    Truncates to `PROCEDURE_ABORT_REASON_MAX_LENGTH` so the AbortProcedure
    handler does not reject the cleanup call. The format leads with
    the step pointer (kind + index + target) so an operator scanning
    the abort reason knows immediately which step in the conducted
    sequence killed the Procedure.
    """
    if failure.step_index is None:
        prefix = f"{failure.source_kind} {failure.target}"
    else:
        prefix = f"{failure.source_kind}[{failure.step_index}] {failure.target}"
    reason = f"{prefix} failed: {failure.error_class}: {failure.message}"
    return reason[:PROCEDURE_ABORT_REASON_MAX_LENGTH]


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
    "CheckCriterion",
    "CheckStep",
    "Conductor",
    "ConductorFailure",
    "ConductorResult",
    "EqualsCriterion",
    "InMemoryActionRegistry",
    "SetpointStep",
    "Step",
    "WithinToleranceCriterion",
]
