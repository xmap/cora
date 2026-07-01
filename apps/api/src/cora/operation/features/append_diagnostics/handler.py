"""Application handler for the `append_diagnostics` slice.

Lazy open-on-first-write + batch append, mirroring `append_activities`. The
conductor is the primary caller (it appends one diagnostic per GP-decided
iteration), but the slice ships the full wire surface (route + tool + authz)
like every other slice, so an operator or tool can read/audit the same path
uniformly and the authz gate is consistent. Steps:

  1. Authorize the principal for `AppendProcedureDiagnostics`.
  2. Load Procedure via `load_procedure` (fold-on-read); reject if NOT Running
     (diagnostics belong to an in-flight steered conduct) ->
     ProcedureStepsLogbookClosedError.
  3. If `procedure.diagnostic_logbook_id` is None: emit
     `ProcedureDiagnosticLogbookOpened` to the Procedure stream.
  4. Read the logbook_id (from existing or just-emitted).
  5. Construct `Diagnostic` rows with the logbook_id + procedure_id +
     correlation/causation from the envelope.
  6. `diagnostic_store.append(rows)`; silent dedup via Postgres PK (or the
     InMemory dict).

Self-healing on ConcurrencyError mirrors `append_activities`: the retry
re-loads the Procedure so a concurrently-opened logbook is seen (and the open
step skipped), or a fresh version is used. Natural idempotence (at-most-one-
open-logbook + entry-store PK) means no idempotency wrapper is needed.
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
    DIAGNOSTIC_LOGBOOK_SCHEMA,
    LOGBOOK_KIND_DIAGNOSTIC,
    Diagnostic,
    DiagnosticStore,
    ProcedureDiagnosticLogbookOpened,
    ProcedureNotFoundError,
    ProcedureStatus,
    ProcedureStepsLogbookClosedError,
    event_type_name,
    load_procedure,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.append_diagnostics.command import (
    AppendProcedureDiagnostics,
    DiagnosticInput,
)

_STREAM_TYPE = "Procedure"
_COMMAND_NAME = "AppendProcedureDiagnostics"
_LAZY_OPEN_MAX_RETRIES = 3
"""Bounded retry for the lazy-open ConcurrencyError loop; mirrors
`append_activities`. Each retry re-loads so a concurrent open is seen."""

_OPEN_STATUSES: frozenset[ProcedureStatus] = frozenset({ProcedureStatus.RUNNING})

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every append_diagnostics handler implements."""

    async def __call__(
        self,
        command: AppendProcedureDiagnostics,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int: ...


def bind(deps: Kernel, *, diagnostic_store: DiagnosticStore) -> Handler:
    """Build an append_diagnostics handler closed over deps + store.

    `diagnostic_store` is BC-internal (constructed in `wire_operation` from
    `deps.pool` for Postgres, or `InMemoryDiagnosticStore` for
    `app_env=test`), per the per-category-writer pattern (mirrors the
    ActivityStore wiring). NOT promoted to Kernel.
    """

    async def handler(
        command: AppendProcedureDiagnostics,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        _log.info(
            "append_diagnostics.start",
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
                "append_diagnostics.denied",
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

            if procedure.diagnostic_logbook_id is not None:
                logbook_id = procedure.diagnostic_logbook_id
                break

            now = deps.clock.now()
            new_logbook_id = deps.id_generator.new_id()
            open_event = ProcedureDiagnosticLogbookOpened(
                procedure_id=command.procedure_id,
                logbook_id=new_logbook_id,
                kind=LOGBOOK_KIND_DIAGNOSTIC,
                schema=DIAGNOSTIC_LOGBOOK_SCHEMA,
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
                    "append_diagnostics.lazy_open_concurrency_retry",
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
        await diagnostic_store.append(rows)

        _log.info(
            "append_diagnostics.success",
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
    entry: DiagnosticInput,
    procedure_id: UUID,
    logbook_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None,
    *,
    fallback_now: object,
) -> Diagnostic:
    """Compose the producer's input plus envelope context into a Diagnostic row."""
    assert isinstance(fallback_now, datetime)
    occurred_at = entry.occurred_at if entry.occurred_at is not None else fallback_now
    return Diagnostic(
        event_id=entry.event_id,
        procedure_id=procedure_id,
        logbook_id=logbook_id,
        iteration_index=entry.iteration_index,
        model_ref=entry.model_ref,
        payload=entry.payload,
        sampled_at=entry.sampled_at,
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )
