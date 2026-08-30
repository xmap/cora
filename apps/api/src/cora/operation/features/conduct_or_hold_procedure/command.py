"""The `ConductOrHoldProcedure` command -- pause-capable conduct entry point.

Like `ConductProcedure`, hands control to the `Conductor` runtime; the one
difference is the failure posture. On a RECOVERABLE step failure (a setpoint
or check: re-drivable / re-runnable on resume) the Conductor PAUSES the
Procedure to `Held` instead of aborting it, so the operator can fix the cause
and `conduct_from` from the pinned resolved steps. A NON-recoverable failure (an
action: an interrupted acquisition), a lifecycle failure, and a mid-execute
cancellation keep `conduct`'s abort posture.

`steps` is the caller-supplied sequence the Conductor walks (same wire shape
as `ConductProcedure`).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from cora.operation.conductor import ConductorFailure, Step, WriteValue
from cora.operation.ports.compute_port import ArtifactRef
from cora.operation.ports.measurement import Measurement


@dataclass(frozen=True)
class ConductOrHoldProcedure:
    """Conduct a Procedure, pausing to Held on a recoverable step failure."""

    procedure_id: UUID
    steps: Sequence[Step]


@dataclass(frozen=True)
class ConductOrHoldProcedureResult:
    """Summary of a `ConductOrHoldProcedure` invocation.

    Mirrors `ConductProcedureResult` plus `held`: True iff a recoverable step
    failure paused the Procedure to `Held` AND the pause transition itself
    succeeded. `held` is what distinguishes a resumable outcome from a
    terminal `Aborted` one: both carry `succeeded=False` + `failure`, but only
    a `held` Procedure can be `conduct_from`-ed. A `held` Procedure whose hold
    transition failed (left Running) reports `held=False`.

    `measurements` / `artifacts` / `outputs` / `substrate_writes` mirror
    `ConductProcedureResult`'s fields verbatim (see there for the full
    rationale): threaded from `ConductorResult`, and present on a HELD
    outcome too -- that is exactly when `substrate_writes` matters most,
    since a Held Procedure's recipe closing steps have not run.
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    held: bool = False
    failure: ConductorFailure | None = None
    actuation_kind: str | None = None
    measurements: tuple[Measurement, ...] = ()
    artifacts: tuple[ArtifactRef, ...] = ()
    outputs: Mapping[str, ArtifactRef] = field(default_factory=dict[str, ArtifactRef])
    substrate_writes: Mapping[str, WriteValue] = field(default_factory=dict[str, WriteValue])
    closing_failures: tuple[ConductorFailure, ...] = ()
    """Every closing step that failed, threaded from `ConductorResult.closing_failures`.

    Always empty on a `held=True` outcome: closing runs only on a real
    terminal (Completed / Aborted), never on Held. Isolated from `failure`:
    a closing failure never flips `succeeded`.
    """
