"""Evolver: replay events to reconstruct Procedure state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `ProcedureEvent` without a matching match arm here.

Status mapping per event type:
  - `ProcedureRegistered`         -> DEFINED   (genesis; universal initial-state convention)
  - `ProcedureStarted`            -> RUNNING   (single-source genesis transition out of Defined)
  - `ProcedureCompleted`          -> COMPLETED (happy-path terminal)
  - `ProcedureAborted`            -> ABORTED   (emergency-exit terminal)
  - `ProcedureTruncated`          -> TRUNCATED (partial-data terminal; mirrors RunTruncated)
  - `ProcedureActivitiesLogbookOpened` -> STATUS UNCHANGED (sets activity_logbook_id;
                                     lazy-open envelope event from
                                     append_activities, orthogonal to lifecycle)

The mapping is hardcoded per match arm -- the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `RunStarted -> RUNNING` / `RunCompleted -> COMPLETED` /
`SubjectMounted -> MOUNTED`.

`target_asset_ids` is converted from `list[UUID]` (event payload)
to `frozenset[UUID]` (state). Order doesn't matter at the state
layer (set semantics for ProcedureStartContext lookup); the payload
already sorted in `to_payload` for persistence determinism.

**Critical invariant**: every transition arm MUST carry `id`, `name`,
`kind`, `target_asset_ids`, `parent_run_id`, `activity_logbook_id`,
`capability_id`, `recipe_id`, `current_iteration_index`,
`iteration_count`, `consecutive_unconverged_iterations`,
`max_consecutive_unconverged_iterations`, AND `actuation_kind` through
from prior state. Constructing `Procedure(id=..., name=...,
status=...)` without explicitly passing the additive fields would
silently WIPE them to defaults (empty frozenset / None / 0). Pinned by
the per-transition preserve-fields tests. Same lesson as Run BC's
evolver docstring.

`actuation_kind` is the one transition-set field: the `ProcedureCompleted`
/ `ProcedureAborted` arms set it from the EVENT (the Conductor's observed
kind for this conduct), every other arm carries `prior.actuation_kind`
(None until a terminal conduct event lands).

The iteration boundary pair folds onto the iteration denorm without
touching `status`: `ProcedureIterationStarted` bumps `iteration_count`
and records the open index in `current_iteration_index`;
`ProcedureIterationEnded` clears `current_iteration_index` back to None
(count unchanged). Both require the Procedure to be Running, enforced
at the deciders (the evolver trusts the decider's guard).

`activity_logbook_id` is set by the `ProcedureActivitiesLogbookOpened` arm
(lazy open-on-first-write triggered by `append_activities`);
all other arms preserve whatever prior state held. Legacy streams
without the logbook event fold with `activity_logbook_id=None`.

The shared `require_state` helper at `cora.infrastructure.evolver`
keeps per-arm bodies short. Hoisted at the rule-of-three trigger
once the 11th identical copy landed; Procedure adopts it on day one
for the new transition arms.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.operation.aggregates.procedure.events import (
    ProcedureAborted,
    ProcedureActivitiesLogbookOpened,
    ProcedureCompleted,
    ProcedureEvent,
    ProcedureIterationEnded,
    ProcedureIterationStarted,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureTruncated,
    RecipeExpansionRecorded,
    ResolvedStepsRecorded,
)
from cora.operation.aggregates.procedure.state import (
    Procedure,
    ProcedureName,
    ProcedureStatus,
)


def evolve(state: Procedure | None, event: ProcedureEvent) -> Procedure:
    """Apply one event to the current state."""
    match event:
        case ProcedureRegistered(
            procedure_id=procedure_id,
            name=name,
            kind=kind,
            target_asset_ids=target_asset_ids,
            parent_run_id=parent_run_id,
            capability_id=capability_id,
            recipe_id=recipe_id,
            max_consecutive_unconverged_iterations=max_consecutive_unconverged_iterations,
        ):
            _ = state  # ProcedureRegistered is the genesis event; prior state ignored
            return Procedure(
                id=procedure_id,
                name=ProcedureName(name),
                kind=kind,
                target_asset_ids=frozenset(target_asset_ids),
                status=ProcedureStatus.DEFINED,
                parent_run_id=parent_run_id,
                activity_logbook_id=None,
                capability_id=capability_id,
                recipe_id=recipe_id,
                current_iteration_index=None,
                iteration_count=0,
                consecutive_unconverged_iterations=0,
                max_consecutive_unconverged_iterations=max_consecutive_unconverged_iterations,
            )
        case ProcedureStarted():
            prior = require_state(state, "ProcedureStarted")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=ProcedureStatus.RUNNING,
                parent_run_id=prior.parent_run_id,
                activity_logbook_id=prior.activity_logbook_id,
                capability_id=prior.capability_id,
                recipe_id=prior.recipe_id,
                current_iteration_index=prior.current_iteration_index,
                iteration_count=prior.iteration_count,
                consecutive_unconverged_iterations=prior.consecutive_unconverged_iterations,
                max_consecutive_unconverged_iterations=(
                    prior.max_consecutive_unconverged_iterations
                ),
                actuation_kind=prior.actuation_kind,
            )
        case ProcedureCompleted(actuation_kind=actuation_kind):
            prior = require_state(state, "ProcedureCompleted")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=ProcedureStatus.COMPLETED,
                parent_run_id=prior.parent_run_id,
                activity_logbook_id=prior.activity_logbook_id,
                capability_id=prior.capability_id,
                recipe_id=prior.recipe_id,
                current_iteration_index=prior.current_iteration_index,
                iteration_count=prior.iteration_count,
                consecutive_unconverged_iterations=prior.consecutive_unconverged_iterations,
                max_consecutive_unconverged_iterations=(
                    prior.max_consecutive_unconverged_iterations
                ),
                # Terminal-set from the conduct's observed kind.
                actuation_kind=actuation_kind,
            )
        case ProcedureAborted(actuation_kind=actuation_kind):
            prior = require_state(state, "ProcedureAborted")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=ProcedureStatus.ABORTED,
                parent_run_id=prior.parent_run_id,
                activity_logbook_id=prior.activity_logbook_id,
                capability_id=prior.capability_id,
                recipe_id=prior.recipe_id,
                current_iteration_index=prior.current_iteration_index,
                iteration_count=prior.iteration_count,
                consecutive_unconverged_iterations=prior.consecutive_unconverged_iterations,
                max_consecutive_unconverged_iterations=(
                    prior.max_consecutive_unconverged_iterations
                ),
                # Terminal-set: routes attempted before the failing step taint it.
                actuation_kind=actuation_kind,
            )
        case ProcedureTruncated():
            prior = require_state(state, "ProcedureTruncated")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=ProcedureStatus.TRUNCATED,
                parent_run_id=prior.parent_run_id,
                activity_logbook_id=prior.activity_logbook_id,
                capability_id=prior.capability_id,
                recipe_id=prior.recipe_id,
                current_iteration_index=prior.current_iteration_index,
                iteration_count=prior.iteration_count,
                consecutive_unconverged_iterations=prior.consecutive_unconverged_iterations,
                max_consecutive_unconverged_iterations=(
                    prior.max_consecutive_unconverged_iterations
                ),
                actuation_kind=prior.actuation_kind,
            )
        case ProcedureActivitiesLogbookOpened(logbook_id=logbook_id):
            # Lazy open-on-first-write: preserve all
            # prior state, set activity_logbook_id. Status NOT touched -- the
            # logbook is orthogonal to lifecycle. Mirrors Run BC's
            # RunObservationLogbookOpened arm exactly.
            prior = require_state(state, "ProcedureActivitiesLogbookOpened")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=prior.status,
                parent_run_id=prior.parent_run_id,
                activity_logbook_id=logbook_id,
                capability_id=prior.capability_id,
                recipe_id=prior.recipe_id,
                current_iteration_index=prior.current_iteration_index,
                iteration_count=prior.iteration_count,
                consecutive_unconverged_iterations=prior.consecutive_unconverged_iterations,
                max_consecutive_unconverged_iterations=(
                    prior.max_consecutive_unconverged_iterations
                ),
                actuation_kind=prior.actuation_kind,
            )
        case RecipeExpansionRecorded():
            # Provenance-only event: leaves Procedure state unchanged.
            # The full denormalized payload (recipe_id, recipe_version,
            # capability_id, capability_version, bindings,
            # expansion_port_version, steps_hash, bindings_hash,
            # step_count) lives in the event stream for audit-replay;
            # there is no projection-folded denorm onto Procedure state
            # beyond what `ProcedureRegistered.recipe_id` already pins.
            return require_state(state, "RecipeExpansionRecorded")
        case ResolvedStepsRecorded():
            # Provenance-only event: leaves Procedure state unchanged. The
            # full resolved step list lives in the event stream for
            # conduct-time replay (resume reads it back); there is no
            # state fold. Mirrors the RecipeExpansionRecorded arm above.
            return require_state(state, "ResolvedStepsRecorded")
        case ProcedureIterationStarted(iteration_index=iteration_index):
            # One convergence-loop iteration began: bump the denorm count
            # and record the open index. Status untouched (iteration is
            # orthogonal to the lifecycle FSM). The strict-successor /
            # no-open-iteration guards live in the start_iteration decider.
            prior = require_state(state, "ProcedureIterationStarted")
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=prior.status,
                parent_run_id=prior.parent_run_id,
                activity_logbook_id=prior.activity_logbook_id,
                capability_id=prior.capability_id,
                recipe_id=prior.recipe_id,
                current_iteration_index=iteration_index,
                iteration_count=prior.iteration_count + 1,
                consecutive_unconverged_iterations=prior.consecutive_unconverged_iterations,
                max_consecutive_unconverged_iterations=(
                    prior.max_consecutive_unconverged_iterations
                ),
                actuation_kind=prior.actuation_kind,
            )
        case ProcedureIterationEnded(converged=converged):
            # The open iteration closed: clear the open-index marker and
            # fold the consecutive-unconverged "patience" streak -- reset to
            # 0 on a converged=True win, otherwise (False OR None) +1. The
            # iteration_count is unchanged (it tracks iterations begun).
            prior = require_state(state, "ProcedureIterationEnded")
            consecutive_unconverged = (
                0 if converged is True else prior.consecutive_unconverged_iterations + 1
            )
            return Procedure(
                id=prior.id,
                name=prior.name,
                kind=prior.kind,
                target_asset_ids=prior.target_asset_ids,
                status=prior.status,
                parent_run_id=prior.parent_run_id,
                activity_logbook_id=prior.activity_logbook_id,
                capability_id=prior.capability_id,
                recipe_id=prior.recipe_id,
                current_iteration_index=None,
                iteration_count=prior.iteration_count,
                consecutive_unconverged_iterations=consecutive_unconverged,
                max_consecutive_unconverged_iterations=(
                    prior.max_consecutive_unconverged_iterations
                ),
                actuation_kind=prior.actuation_kind,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ProcedureEvent]) -> Procedure | None:
    """Replay a stream of events from the empty initial state."""
    state: Procedure | None = None
    for event in events:
        state = evolve(state, event)
    return state
