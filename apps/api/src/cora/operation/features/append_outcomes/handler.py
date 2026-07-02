"""Application handler for the `append_outcomes` slice.

Lazy open-on-first-write + batch append, mirroring `append_diagnostics`. The
conductor is the primary caller (it appends one outcome per steered iteration),
but the slice ships the full wire surface (route + tool + authz) like every
other slice. Steps:

  1. Authorize the principal for `AppendProcedureOutcomes`.
  2. Load Procedure via `load_procedure` (fold-on-read); reject if NOT Running
     (outcomes belong to an in-flight steered conduct) ->
     ProcedureStepsLogbookClosedError.
  3. If `procedure.outcome_logbook_id` is None: emit
     `ProcedureOutcomeLogbookOpened` to the Procedure stream.
  4. Read the logbook_id (from existing or just-emitted).
  5. Construct `Outcome` rows with the logbook_id + procedure_id +
     correlation/causation from the envelope.
  6. `outcome_store.append(rows)`; silent dedup via Postgres PK (or the
     InMemory dict).

Self-healing on ConcurrencyError mirrors `append_diagnostics`: the retry
re-loads the Procedure so a concurrently-opened logbook is seen (and the open
step skipped). Natural idempotence (at-most-one-open-logbook + entry-store PK)
means no idempotency wrapper is needed.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.aggregates.procedure import (
    LOGBOOK_KIND_OUTCOME,
    OUTCOME_LOGBOOK_SCHEMA,
    Outcome,
    OutcomeStore,
    ProcedureNotFoundError,
    ProcedureOutcomeLogbookOpened,
    ProcedureStatus,
    ProcedureStepsLogbookClosedError,
    event_type_name,
    load_procedure,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.append_outcomes.command import (
    AppendProcedureOutcomes,
    OutcomeInput,
)

_STREAM_TYPE = "Procedure"
_COMMAND_NAME = "AppendProcedureOutcomes"
_LAZY_OPEN_MAX_RETRIES = 3
"""Bounded retry for the lazy-open ConcurrencyError loop; mirrors
`append_diagnostics`. Each retry re-loads so a concurrent open is seen."""

_OPEN_STATUSES: frozenset[ProcedureStatus] = frozenset({ProcedureStatus.RUNNING})

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every append_outcomes handler implements."""

    async def __call__(
        self,
        command: AppendProcedureOutcomes,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int: ...


def bind(deps: Kernel, *, outcome_store: OutcomeStore) -> Handler:
    """Build an append_outcomes handler closed over deps + store.

    `outcome_store` is BC-internal (constructed in `wire_operation` from
    `deps.pool` for Postgres, or `InMemoryOutcomeStore` for `app_env=test`),
    per the per-category-writer pattern (mirrors the DiagnosticStore wiring).
    NOT promoted to Kernel.
    """

    async def handler(
        command: AppendProcedureOutcomes,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        _log.info(
            "append_outcomes.start",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            entry_count=len(command.entries),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        authz = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(authz, Deny):
            _log.info(
                "append_outcomes.denied",
                command_name=_COMMAND_NAME,
                procedure_id=str(command.procedure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=authz.reason,
            )
            raise UnauthorizedError(authz.reason)

        opened_logbook_now = False
        logbook_id: UUID | None = None
        for attempt in range(_LAZY_OPEN_MAX_RETRIES):
            procedure = await load_procedure(deps.event_store, command.procedure_id)
            if procedure is None:
                raise ProcedureNotFoundError(command.procedure_id)

            if procedure.status not in _OPEN_STATUSES:
                raise ProcedureStepsLogbookClosedError(procedure.id, procedure.status)

            if procedure.outcome_logbook_id is not None:
                logbook_id = procedure.outcome_logbook_id
                break

            now = deps.clock.now()
            new_logbook_id = deps.id_generator.new_id()
            open_event = ProcedureOutcomeLogbookOpened(
                procedure_id=command.procedure_id,
                logbook_id=new_logbook_id,
                kind=LOGBOOK_KIND_OUTCOME,
                schema=OUTCOME_LOGBOOK_SCHEMA,
                occurred_at=now,
            )
            stored_open = to_new_event(
                event_type=event_type_name(open_event),
                payload=to_payload(open_event),
                occurred_at=open_event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            _, current_version = await deps.event_store.load(
                stream_type=_STREAM_TYPE,
                stream_id=command.procedure_id,
            )
            try:
                await deps.event_store.append(
                    stream_type=_STREAM_TYPE,
                    stream_id=command.procedure_id,
                    expected_version=current_version,
                    events=[stored_open],
                )
            except ConcurrencyError:
                _log.info(
                    "append_outcomes.lazy_open_concurrency_retry",
                    command_name=_COMMAND_NAME,
                    procedure_id=str(command.procedure_id),
                    attempt=attempt,
                )
                continue
            logbook_id = new_logbook_id
            opened_logbook_now = True
            break
        else:  # pragma: no cover  # retry-exhaustion guard
            raise ConcurrencyError(
                stream_type=_STREAM_TYPE,
                stream_id=command.procedure_id,
                expected=-1,
                actual=-1,
            )

        assert logbook_id is not None  # loop guarantees this on break

        rows = [
            _build_row(
                entry,
                command.procedure_id,
                logbook_id,
                correlation_id,
                causation_id,
                fallback_now=deps.clock.now(),
            )
            for entry in command.entries
        ]
        await outcome_store.append(rows)

        _log.info(
            "append_outcomes.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            logbook_id=str(logbook_id),
            entry_count=len(rows),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            opened_logbook=opened_logbook_now,
        )
        return len(rows)

    return handler


def _build_row(
    entry: OutcomeInput,
    procedure_id: UUID,
    logbook_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None,
    *,
    fallback_now: object,
) -> Outcome:
    """Compose the producer's input plus envelope context into an Outcome row."""
    assert isinstance(fallback_now, datetime)
    occurred_at = entry.occurred_at if entry.occurred_at is not None else fallback_now
    return Outcome(
        event_id=entry.event_id,
        procedure_id=procedure_id,
        logbook_id=logbook_id,
        iteration_index=entry.iteration_index,
        point=dict(entry.point),
        measurements=[dict(m) for m in entry.measurements],
        succeeded=entry.succeeded,
        actuation_kind=entry.actuation_kind,
        sampled_at=entry.sampled_at,
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )
