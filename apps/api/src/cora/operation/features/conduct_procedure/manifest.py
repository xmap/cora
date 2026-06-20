"""Pure decision helper: pin the resolved step list at conduct start.

The `conduct_procedure` orchestration handler calls this AFTER it has
resolved the final step list (recipe re-expansion + pseudoaxis +
constituent resolution) and BEFORE handing the list to the Conductor, so
every conduct pins its manifest before any step executes.

Emitted inline from the conduct flow rather than via a dedicated command
slice: `ResolvedStepsRecorded` is an internal provenance event with no
operator entry point, exactly like `RecipeExpansionRecorded`. Kept as a
pure function so the decision is unit-testable without an event store.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureStatus,
    ResolvedStepsRecorded,
)


def decide_resolved_steps_recorded(
    state: Procedure | None,
    resolved_steps: Sequence[Mapping[str, Any]],
    *,
    now: datetime,
) -> list[ResolvedStepsRecorded]:
    """Pin the resolved step list iff the Procedure is pre-conduct (Defined).

    Returns a single `ResolvedStepsRecorded` when `state` is `Defined`
    (the normal conduct path, before `start_procedure` transitions it to
    `Running`). Returns `[]` when `state` is None or not `Defined`: a
    conduct of a missing / already-running / terminal Procedure records no
    manifest and lets the Conductor's `start_procedure` produce the normal
    lifecycle failure, preserving the conduct route's failures-in-body
    contract instead of raising a fresh HTTP error here.
    """
    if state is None or state.status is not ProcedureStatus.DEFINED:
        return []
    steps = tuple(dict(step) for step in resolved_steps)
    return [
        ResolvedStepsRecorded(
            procedure_id=state.id,
            resolved_steps=steps,
            step_count=len(steps),
            occurred_at=now,
        )
    ]
