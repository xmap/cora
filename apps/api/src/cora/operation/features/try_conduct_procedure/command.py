"""The `TryConductProcedure` command -- pause-capable conduct entry point.

Like `ConductProcedure`, hands control to the `Conductor` runtime; the one
difference is the failure posture. On a RECOVERABLE step failure (a setpoint
or check: re-drivable / re-runnable on resume) the Conductor PAUSES the
Procedure to `Held` instead of aborting it, so the operator can fix the cause
and `reconduct` from the pinned resolved steps. A NON-recoverable failure (an
action: an interrupted acquisition), a lifecycle failure, and a mid-execute
cancellation keep `conduct`'s abort posture.

`steps` is the caller-supplied sequence the Conductor walks (same wire shape
as `ConductProcedure`).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from cora.operation.conductor import ConductorFailure, Step


@dataclass(frozen=True)
class TryConductProcedure:
    """Conduct a Procedure, pausing to Held on a recoverable step failure."""

    procedure_id: UUID
    steps: Sequence[Step]


@dataclass(frozen=True)
class TryConductProcedureResult:
    """Summary of a `TryConductProcedure` invocation.

    Mirrors `ConductProcedureResult` plus `held`: True iff a recoverable step
    failure paused the Procedure to `Held` AND the pause transition itself
    succeeded. `held` is what distinguishes a resumable outcome from a
    terminal `Aborted` one: both carry `succeeded=False` + `failure`, but only
    a `held` Procedure can be `reconduct`-ed. A `held` Procedure whose hold
    transition failed (left Running) reports `held=False`.
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    held: bool = False
    failure: ConductorFailure | None = None
    actuation_kind: str | None = None
