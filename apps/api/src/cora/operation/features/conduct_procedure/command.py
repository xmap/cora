"""The `ConductProcedure` command -- operator-facing entry for `Conductor.conduct()`.

Unlike most slice commands, `ConductProcedure` does not directly write
to an aggregate's event stream. It hands control to the
`cora.operation.conductor.Conductor` runtime, which orchestrates
the full Procedure lifecycle: `start_procedure` ->
walk-supplied-steps -> `complete_procedure` (on success) or
`abort_procedure` (on step failure). The handler returns a
`ConductProcedureResult` summarising the run; failures are encoded in
that result, not raised as exceptions, so a single HTTP / MCP
response shape covers every outcome the operator needs to triage.

`steps` is the caller-supplied sequence the Conductor walks.
Substrate-agnostic: setpoint addresses parse inside the routed
`ControlPort` adapter, action names look up in the `ActionRegistry`,
check criteria evaluate against the read `Measurement.value`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from cora.operation.conductor import ConductorFailure, Step
from cora.operation.ports.measurement import Measurement


@dataclass(frozen=True)
class ConductProcedure:
    """Invoke the Conductor against an existing Procedure + step list."""

    procedure_id: UUID
    steps: Sequence[Step]


@dataclass(frozen=True)
class ConductProcedureResult:
    """Summary of a `ConductProcedure` invocation.

    Mirrors `ConductorResult` shape verbatim (procedure_id +
    completed_count + optional failure) so the wire response stays
    decoupled from the in-process Conductor type and the
    application-layer slice owns its return-type contract.

    `actuation_kind` is the raw `ActuationKind` value (Physical /
    Simulated / Hybrid) the Conductor observed across the conduct, or
    None when nothing instrumented was actuated (no routing table, or
    no control-port write). Surfaced for operator visibility; the same
    value is the one the Conductor records on the Procedure terminal
    event, where the Data BC reads it back to gate promotion.

    `measurements` carries the `Measurement`s every `ComputeStep` in the
    conduct produced (slice 6a), threaded from `ConductorResult.measurements`,
    so the caller reads the produced measurements (a detector pixel size that
    homes to a Calibration) without re-parsing the activity log. Empty on
    a conduct with no ComputeStep.
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: ConductorFailure | None = None
    actuation_kind: str | None = None
    measurements: tuple[Measurement, ...] = ()
