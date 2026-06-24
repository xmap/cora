"""Composition-root glue: complete a Run from a conducted Procedure-phase.

`conduct_phase_then_complete_run` is the autonomous bridge the
acquisition-Run watch-item called for. The boundary memo retired the
name "AcquisitionRuntime" for it: this is glue, not a runtime, and not
acquisition-specific. It conducts a Procedure that is a PHASE of a
parent Run, then drives the parent Run to its terminal carrying the
conduct's observed `actuation_kind`: `complete_run` on success,
`abort_run` on a conduct failure.

## Why it lives at `cora.api`

It needs both `conduct_procedure` (an Operation-BC handler that wraps
the `Conductor` over `ControlPort`) and `complete_run` / `abort_run`
(Run-BC handlers). tach forbids `cora.run -> cora.operation`, and
Operation imports only `cora.run.aggregates` (not Run features), so no
BC can host it. It lives at the composition root, exactly as the
`Reckoner` does.

## Relation to the Reckoner

The `Reckoner` conducts a compute Run end-to-end over `ComputePort` and
completes it inline (one class, because a compute job is single-shot).
The physical path splits: the `Conductor` drives the Procedure-PHASE and
completes the PROCEDURE; this glue completes the parent RUN with the
phase's kind. It is the "complete the Run" half the Reckoner has inline,
not a fourth port-driver runtime.

## Terminal-rejection posture

The abort terminal is best-effort: a failed conduct's diagnostic
(`succeeded=False` + `failure`) must survive even if the Run cannot be
transitioned (already terminal, or concurrently aborted), so a rejection
there is suppressed rather than allowed to mask the conduct failure. This
mirrors the Reckoner's and Conductor's best-effort abort. A
complete-terminal rejection, by contrast, propagates: "the conduct
succeeded but the Run could not be completed" is an exceptional condition
the caller must see, not swallow.

## Why the Run carries the phase's kind

The simulator promote-gate blocks Datasets whose producing actuation was
Simulated / Hybrid. A conducted Run completed with `actuation_kind` None
re-opens that gate for Run-produced Datasets (the gate's
unprovable-provenance arm keys on a producing Procedure, not a Run). The
phase Procedure's `ConductProcedureResult.actuation_kind` is already the
merged honest kind (the Conductor folds it across any hold/resume); this
glue threads that single value onto the Run terminal. A single SET is
correct while a Run wraps one phase; cross-phase merge is a multi-phase
(regime-2) concern, deferred.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.features.conduct_procedure.command import ConductProcedure
from cora.run.features.abort_run.command import AbortRun
from cora.run.features.complete_run.command import CompleteRun

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from cora.operation.conductor import ConductorFailure, Step
    from cora.operation.features.conduct_procedure.handler import Handler as ConductProcedureHandler
    from cora.run.features.abort_run.handler import Handler as AbortRunHandler
    from cora.run.features.complete_run.handler import Handler as CompleteRunHandler

# Bound so a derived abort reason always fits RunAbortReason (1-500
# chars after trim); the substrate detail tail is truncated to leave
# headroom for the prefix.
_REASON_MAX = 480


@dataclass(frozen=True)
class RunPhaseConductResult:
    """Outcome of a `conduct_phase_then_complete_run` call.

    `succeeded` mirrors the phase conduct's outcome (and so which Run
    terminal fired: `complete_run` when True, `abort_run` when False).
    `actuation_kind` is the raw kind the Conductor observed for the
    phase (threaded onto the Run terminal); `completed_count` is the
    phase's fully-run step count; `failure` is the phase's first halt
    condition, or None on success.
    """

    run_id: UUID
    procedure_id: UUID
    succeeded: bool
    actuation_kind: str | None
    completed_count: int
    failure: ConductorFailure | None = None


async def conduct_phase_then_complete_run(
    *,
    run_id: UUID,
    procedure_id: UUID,
    conduct_procedure: ConductProcedureHandler,
    complete_run: CompleteRunHandler,
    abort_run: AbortRunHandler,
    steps: Sequence[Step] = (),
    principal_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
    surface_id: UUID = NIL_SENTINEL_ID,
) -> RunPhaseConductResult:
    """Conduct a Procedure-phase of a Run, then drive the Run to its terminal.

    Conducts `procedure_id` (the phase) via `conduct_procedure`, then on
    success completes the parent `run_id` carrying the phase's observed
    `actuation_kind`, or on a conduct failure aborts the Run with a
    reason derived from the failure (still carrying the kind, so even a
    failed conduct taints any Dataset that references the Run). The Run
    terminal SETs the kind: a single phase contributes a single
    already-merged value (cross-phase merge is deferred to the
    multi-phase regime). `steps` is empty for a recipe-driven phase (the
    handler re-expands the pinned template).
    """
    envelope: dict[str, Any] = {
        "principal_id": principal_id,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "surface_id": surface_id,
    }

    result = await conduct_procedure(
        ConductProcedure(procedure_id=procedure_id, steps=steps),
        **envelope,
    )

    if result.succeeded:
        await complete_run(
            CompleteRun(run_id=run_id, actuation_kind=result.actuation_kind),
            **envelope,
        )
    else:
        # Best-effort abort: a failed conduct's diagnostic (succeeded=False +
        # failure) must survive even if the Run cannot be transitioned (already
        # terminal, or concurrently aborted), so a rejection here is suppressed
        # rather than allowed to mask the conduct failure. Mirrors the Reckoner
        # and the Conductor.
        with contextlib.suppress(Exception):
            await abort_run(
                AbortRun(
                    run_id=run_id,
                    reason=_abort_reason(result.failure),
                    actuation_kind=result.actuation_kind,
                ),
                **envelope,
            )

    return RunPhaseConductResult(
        run_id=run_id,
        procedure_id=procedure_id,
        succeeded=result.succeeded,
        actuation_kind=result.actuation_kind,
        completed_count=result.completed_count,
        failure=result.failure,
    )


def _abort_reason(failure: ConductorFailure | None) -> str:
    """Derive a Run abort reason from the phase conduct's failure."""
    if failure is None:
        return "phase conduct failed"
    where = f"{failure.source_kind} {failure.target}".strip()
    detail = f"phase conduct failed at {where}: {failure.error_class}: {failure.message}"
    trimmed = detail.strip()
    if len(trimmed) <= _REASON_MAX:
        return trimmed
    return trimmed[: _REASON_MAX - 3] + "..."


__all__ = ["RunPhaseConductResult", "conduct_phase_then_complete_run"]
