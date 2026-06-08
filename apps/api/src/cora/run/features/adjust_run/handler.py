"""Application handler for the `adjust_run` slice.

Longhand handler (not the `make_run_update_handler` factory): the
factory loads ONLY the target Run stream, but adjust_run needs to
ALSO pre-load Plan -> Practice -> Method to surface the schema for
merged-result validation. Mirrors `start_run`'s longhand handler.

## Pre-load order

  1. `load_run(run_id)` → if None, `RunNotFoundError`
  2. `load_plan(run.plan_id)` → if None, `PlanNotFoundError`
  3. `load_practice(plan.practice_id)` → if None, `PracticeNotFoundError`
     (defensive — Plan was bound against a real Practice; serious
     stream corruption if missing)
  4. `load_method(practice.method_id)` → if None, `MethodNotFoundError`

The Method's `parameters_schema` is then bundled with the source-state
Run into `RunAdjustContext`. The pure decider validates source-state +
merged-against-schema and emits `RunAdjusted`. The handler wraps the
event via `to_new_event` and appends to the Run stream at the loaded
version (optimistic-concurrency token).

## Decision-causation NOT verified

`command.decided_by_decision_id` (when supplied) is carried verbatim
onto the event payload. The handler does NOT load the Decision aggregate;
existence verification follows the cross-BC eventual-consistency stance
(Trust.Conduit / Asset parent / Procedure target / Campaign lead_actor /
Run.subject_id precedent). Cross-BC reference verification belongs in
projection consumers, not the write path.

## Idempotency

The slice is wrapped with `with_idempotency` at wire.py (operator retries
on flaky network must NOT double-apply patches; same logic as
amend_clearance + add_run_to_campaign). The cache key includes the
command hash, so two distinct AdjustRun requests get distinct entries;
the same request retried gets the cached 204.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.method import MethodNotFoundError, load_method
from cora.recipe.aggregates.plan import PlanNotFoundError, load_plan
from cora.recipe.aggregates.practice import PracticeNotFoundError, load_practice
from cora.run.aggregates.run import (
    RunNotFoundError,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.run.aggregates.run.evolver import fold
from cora.run.errors import UnauthorizedError
from cora.run.features.adjust_run.command import AdjustRun
from cora.run.features.adjust_run.context import RunAdjustContext
from cora.run.features.adjust_run.decider import decide
from cora.shared.identity import ActorId

_STREAM_TYPE = "Run"
_COMMAND_NAME = "AdjustRun"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare adjust_run handler — what `bind()` returns.

    Returns None (the slice is 204-on-success at REST). Has no
    idempotency_key kwarg; `with_idempotency` at wire.py adds it.
    """

    async def __call__(
        self,
        command: AdjustRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


class IdempotentHandler(Protocol):
    """adjust_run handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: AdjustRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an adjust_run handler closed over the shared deps."""

    async def handler(
        command: AdjustRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "adjust_run.start",
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
            patch_key_count=len(command.parameters_patch),
            decided_by_decision_id=(
                str(command.decided_by_decision_id)
                if command.decided_by_decision_id is not None
                else None
            ),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "adjust_run.denied",
                command_name=_COMMAND_NAME,
                run_id=str(command.run_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Pre-load the Run stream once: we need both the folded Run
        # (for status / effective_parameters / plan_id) AND the raw
        # version (optimistic-concurrency token for the append). Fold
        # inline rather than re-loading via `load_run`.
        stored, current_version = await deps.event_store.load(_STREAM_TYPE, command.run_id)
        run = fold([from_stored(s) for s in stored])
        if run is None:
            raise RunNotFoundError(command.run_id)

        # Walk the Recipe chain to pull the Method's parameters_schema.
        # Same path as start_run's handler.
        plan = await load_plan(deps.event_store, run.plan_id)
        if plan is None:
            raise PlanNotFoundError(run.plan_id)
        practice = await load_practice(deps.event_store, plan.practice_id)
        if practice is None:
            raise PracticeNotFoundError(plan.practice_id)
        method = await load_method(deps.event_store, practice.method_id)
        if method is None:
            raise MethodNotFoundError(practice.method_id)

        context = RunAdjustContext(
            run=run,
            method_parameters_schema=method.parameters_schema,
        )

        now = deps.clock.now()

        events = decide(
            state=run,
            command=command,
            context=context,
            adjusted_by=ActorId(principal_id),
            now=now,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in events
        ]

        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.run_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "adjust_run.success",
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
            method_id=str(method.id),
            patch_key_count=len(command.parameters_patch),
            effective_key_count=len(events[0].effective_parameters),
            schema_present=method.parameters_schema is not None,
            decided_by_decision_id=(
                str(command.decided_by_decision_id)
                if command.decided_by_decision_id is not None
                else None
            ),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )

    return handler
