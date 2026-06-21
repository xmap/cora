"""Application handler for the `append_observations` slice.

Lazy open-on-first-write + batch append. Two-step non-transactional
write mirroring Decision BC's `append_inferences` precedent:

  1. Load Run via `load_run` (fold-on-read).
  2. Reject if Run is in a terminal status (RunObservationLogbookClosedError).
  3. If `run.observation_logbook_id` is None: emit
     `RunObservationLogbookOpened` to the Run stream.
  4. Read the logbook_id (from existing or just-emitted).
  5. Construct `Observation` rows with the logbook_id +
     correlation_id + run_id from the envelope.
  6. `observation_store.append(rows)`, silent dedup via Postgres PK
     (or InMemory dict setdefault).

## Self-healing on failure

  - Step 3 fails (concurrency on Run stream): handler retries from
    step 1; the conflicting writer either also opened a observation
    logbook (we now see it open on reload, skip step 3) OR
    registered a different event entirely (re-validate terminal
    status, then proceed).
  - Step 6 fails after step 3 succeeded: dangling open logbook with
    no entries. The next call sees the logbook is open, skips step
    3, and retries the entry append. UUIDv7 PK + at-most-one-open
    invariant make this fully recoverable.

## Why not idempotency-wrapped

Natural idempotence: the at-most-one-open-logbook invariant catches
double-opens; entry-store PK catches double-appends. Wrapping the
slice in `with_idempotency` would add no value beyond what the
domain already guarantees.

## Defensive `sampling_procedure` validation

Pydantic at the API layer catches invalid values via `Literal[...]`
on the request body. The handler ALSO validates against
`SAMPLING_PROCEDURE_VALUES` so direct in-process callers (sagas,
tests) get the same protection. Same defensive-validation posture
as the bounded-text VOs across the codebase.
"""

import math
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import (
    LOGBOOK_KIND_OBSERVATION,
    OBSERVATION_LOGBOOK_SCHEMA,
    SAMPLING_PROCEDURE_VALUES,
    ChannelName,
    InvalidObservationValueError,
    InvalidSamplingProcedureError,
    Observation,
    ObservationStore,
    RunNotFoundError,
    RunObservationLogbookClosedError,
    RunObservationLogbookOpened,
    RunStatus,
    event_type_name,
    load_run,
    to_payload,
)
from cora.run.errors import UnauthorizedError
from cora.run.features.append_observations.command import (
    AppendObservations,
    ObservationInput,
)

_STREAM_TYPE = "Run"
_COMMAND_NAME = "AppendObservations"
_LAZY_OPEN_MAX_RETRIES = 3
"""Bounded retry count for the lazy-open ConcurrencyError loop.

Each retry re-loads the Run (so subsequent attempts see any
concurrently-opened logbook + skip the open step). 3 attempts
covers the realistic burst-write window; beyond that we surface
the conflict as ConcurrencyError. Mirrors Decision BC's bound."""

_OPEN_STATUSES: frozenset[RunStatus] = frozenset({RunStatus.RUNNING, RunStatus.HELD})

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every append_observations handler implements."""

    async def __call__(
        self,
        command: AppendObservations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int: ...


def bind(deps: Kernel, *, observation_store: ObservationStore) -> Handler:
    """Build an append_observations handler closed over deps + store.

    `observation_store` is BC-internal (constructed in `wire_run` from
    `deps.pool` for Postgres, or `InMemoryObservationStore` for
    `app_env=test`). Not promoted to Kernel per the per-category-
    writer pattern locked at gate-review L9 (mirrors Conduit's
    VerdictStore and Decision's InferenceStore).
    """

    async def handler(
        command: AppendObservations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        _log.info(
            "append_observations.start",
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
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
                "append_observations.denied",
                command_name=_COMMAND_NAME,
                run_id=str(command.run_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=authz.reason,
            )
            raise UnauthorizedError(authz.reason)

        # Defensive per-entry validation. Pydantic catches these at the
        # API boundary; the in-handler checks protect direct callers
        # (sagas, tests) and provide a single, consistent error class
        # per failure mode regardless of caller path.
        for entry in command.entries:
            ChannelName(entry.channel_name)  # raises InvalidChannelNameError
            if math.isnan(entry.value) or math.isinf(entry.value):
                raise InvalidObservationValueError(entry.value)
            if entry.sampling_procedure not in SAMPLING_PROCEDURE_VALUES:
                raise InvalidSamplingProcedureError(
                    entry.sampling_procedure, SAMPLING_PROCEDURE_VALUES
                )

        # Resolve the observation logbook id, opening it lazily on the
        # first append. Retries on ConcurrencyError (a parallel writer
        # incrementing the Run stream's version between our load +
        # append): the retry re-loads, and either sees the logbook now
        # open (skips the open) or proceeds with a fresh version.
        # Bounded retry, beyond _LAZY_OPEN_MAX_RETRIES the conflict
        # surfaces as ConcurrencyError rather than infinite spin.
        opened_logbook_now = False
        logbook_id: UUID | None = None
        for attempt in range(_LAZY_OPEN_MAX_RETRIES):
            run = await load_run(deps.event_store, command.run_id)
            if run is None:
                raise RunNotFoundError(command.run_id)

            # Status guard: terminal Runs implicitly close the logbook.
            # Re-checked on every retry attempt because a concurrent
            # writer could have transitioned the Run to terminal
            # between our prior load and this retry.
            if run.status not in _OPEN_STATUSES:
                raise RunObservationLogbookClosedError(run.id, run.status)

            if run.observation_logbook_id is not None:
                logbook_id = run.observation_logbook_id
                break

            now = deps.clock.now()
            new_logbook_id = deps.id_generator.new_id()
            open_event = RunObservationLogbookOpened(
                run_id=command.run_id,
                logbook_id=new_logbook_id,
                kind=LOGBOOK_KIND_OBSERVATION,
                schema=OBSERVATION_LOGBOOK_SCHEMA,
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
            # The version we just folded equals the events count we
            # loaded; pass it as expected_version (Postgres event
            # store uses optimistic concurrency on this).
            _, current_version = await deps.event_store.load(
                stream_type=_STREAM_TYPE,
                stream_id=command.run_id,
            )
            try:
                await deps.event_store.append(
                    stream_type=_STREAM_TYPE,
                    stream_id=command.run_id,
                    expected_version=current_version,
                    events=[stored_open],
                )
            except ConcurrencyError:
                _log.info(
                    "append_observations.lazy_open_concurrency_retry",
                    command_name=_COMMAND_NAME,
                    run_id=str(command.run_id),
                    attempt=attempt,
                )
                continue
            logbook_id = new_logbook_id
            opened_logbook_now = True
            break
        else:  # pragma: no cover  # retry-exhaustion guard
            raise ConcurrencyError(
                stream_type=_STREAM_TYPE,
                stream_id=command.run_id,
                expected=-1,
                actual=-1,
            )

        assert logbook_id is not None  # loop guarantees this on break

        rows = [
            _build_row(
                entry,
                command.run_id,
                logbook_id,
                principal_id,
                correlation_id,
                causation_id,
                fallback_now=deps.clock.now(),
            )
            for entry in command.entries
        ]
        await observation_store.append(rows)

        _log.info(
            "append_observations.success",
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
            logbook_id=str(logbook_id),
            entry_count=len(rows),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            opened_logbook=opened_logbook_now,
        )
        return len(rows)

    return handler


def _build_row(
    entry: ObservationInput,
    run_id: UUID,
    logbook_id: UUID,
    actor_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None,
    *,
    fallback_now: object,
) -> Observation:
    """Compose the producer's input plus envelope context into a
    Observation row ready for the store.

    `occurred_at` defaults to `fallback_now` (deps.clock.now()) when
    the producer omits it. `actor_id` is the principal that submitted
    the command (taken from the envelope, not from the entry, per
    PII-vault posture).
    """
    assert isinstance(fallback_now, datetime)
    occurred_at = entry.occurred_at if entry.occurred_at is not None else fallback_now
    return Observation(
        event_id=entry.event_id,
        run_id=run_id,
        logbook_id=logbook_id,
        actor_id=actor_id,
        command_name=_COMMAND_NAME,
        channel_name=entry.channel_name,
        value=entry.value,
        units=entry.units,
        sampling_procedure=entry.sampling_procedure,
        sampled_at=entry.sampled_at,
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        causation_id=causation_id,
        is_simulated=entry.is_simulated,
    )
