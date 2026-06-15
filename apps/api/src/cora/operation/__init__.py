"""Operation bounded context.

Owns episodic operational work in CORA (ISA-106 lens):

  - `Procedure` aggregate: one execution of an episodic operational
    task — bakeout, characterization, optical alignment, beam-mode
    change, recovery procedure, ID maintenance, KB switching. Each
    Procedure has sequenced steps; each step has a Setpoint / Action
    / Check triplet (CORA's rename of ISA-106's canonical
    Command/Perform/Verify to avoid catastrophic CQRS collision).

Track B BC (ISA-106 lens). Independent of Track A (Recipe / Subject
/ Data). Distinct from ISA-88 batch operations which the Run BC
follows; the BC is named `Operation` (publicly committed in BC map +
phase plan) despite the ISA-88 naming overlap (ISA-88 has Operation
as mid-tier in P -> UP -> Op -> Phase). The collision is
documented + manageable; renaming the publicly-committed BC name was
rejected as too high churn for marginal value. See
[[project_operation_design]] §Locks for the rename-rejection
rationale.

Slices: `register_procedure` (genesis -> Defined), `start_procedure`
/ `complete_procedure` / `abort_procedure` / `truncate_procedure`
(FSM transitions), `append_activities` (per-step logbook with
Setpoint/Action/Check rows mirroring Run BC's Observation channel),
`get_procedure` (fold-on-read), `list_procedures` (projection-backed).

## Step vs Activity altitude split

Two `Step`-shaped concepts live in this BC at different altitudes,
deliberately:

  - **Runtime `Step` union** (`conductor.py`): the discriminated
    union `SetpointStep | ActionStep | CheckStep` — the IN-FLIGHT
    spec the Conductor walks during a Procedure execution. Each
    variant is what the conductor IS TOLD TO DO at one step.
  - **Persisted `Activity` entry** (`aggregates/procedure/entries.py`):
    one row per executed step, capturing WHAT HAPPENED (the step
    that ran, with its result). Path C polymorphic table with
    `step_kind` discriminator carrying the runtime variant's name
    (`setpoint` / `action` / `check`).

The relationship: each runtime `Step` execution writes one
`Activity` entry through the `ActivityStore` port. Conductor's
`SetpointStep | ActionStep | CheckStep` are the SPEC; the
`entries_operation_procedure_activities` rows are the LOG.

The 2026-06-09 logbook-entry rename (project_logbook_entry_storage
"Convention shift") split the names to make this altitude
separation legible: pre-rename, `ProcedureStep` (the entry class)
shared the noun with the runtime variants and read as if it was
just another `Step`. Post-rename, `Activity` carries its own
semantic anchor (PROV-O `prov:Activity` = "thing that occurred and
acted upon entities") so operators reading "the activity log for
procedure X" and reviewers reading "show me the steps that ran"
both have unambiguous vocabulary at their altitude.
"""

from cora.operation._projections import register_operation_projections
from cora.operation.errors import UnauthorizedError
from cora.operation.routes import register_operation_routes
from cora.operation.tools import register_operation_tools
from cora.operation.wire import OperationHandlers, wire_operation

__all__ = [
    "OperationHandlers",
    "UnauthorizedError",
    "register_operation_projections",
    "register_operation_routes",
    "register_operation_tools",
    "wire_operation",
]
