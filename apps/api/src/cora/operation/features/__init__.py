"""Vertical slices for the Operation BC.

Slices:
  - `register_procedure` (genesis -> Defined; create-style,
    idempotency-wrapped)
  - `get_procedure` (read; fold-on-read)

FSM-closure transitions:
  - `start_procedure` (Defined -> Running; with ProcedureStartContext
    pre-loading target Assets and rejecting Decommissioned, mirroring
    RunStartContext from the Run BC)
  - `complete_procedure` (Running -> Completed; happy path)
  - `abort_procedure` (Running -> Aborted; emergency exit with reason)

Per-step logbook slice:
  - `append_activities` (entry-shape slice; writes one
    Setpoint/Action/Check entry per step to the
    entries_operation_procedure_activities logbook table; mirrors
    append_observations from the Run BC, with lazy-open envelope event
    `ProcedureActivitiesLogbookOpened` on first append)

Partial-data terminal (triggers the `make_procedure_update_handler`
factory hoist at rule-of-three since
this is the third update slice):
  - `truncate_procedure` (Running -> Truncated; partial-data terminal
    mirroring RunTruncated; reason + optional interrupted_at)

Resumable-conduct pause/resume pair (Tier 1 of
[[project_resumable_conduct_design]]; the state name mirrors
`RunStatus.HELD`):
  - `hold_procedure` (Running -> Held; operator-pause of a halted
    conduct, required reason)
  - `resume_procedure` (Held -> Running; carries the
    `re_establishment_boundary` the Conductor replays from)

Read side:
  - projection (`proj_operation_procedure_summary`) + `list_procedures`
    (cursor-paginated; status / kind / parent_run_id / target_asset_id
    filters)
"""

from cora.operation.features import (
    abort_procedure,
    append_activities,
    complete_procedure,
    get_procedure,
    hold_procedure,
    list_procedures,
    reconduct_procedure,
    register_procedure,
    resume_procedure,
    start_procedure,
    truncate_procedure,
)

__all__ = [
    "abort_procedure",
    "append_activities",
    "complete_procedure",
    "get_procedure",
    "hold_procedure",
    "list_procedures",
    "reconduct_procedure",
    "register_procedure",
    "resume_procedure",
    "start_procedure",
    "truncate_procedure",
]
