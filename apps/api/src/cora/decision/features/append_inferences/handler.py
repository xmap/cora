"""Application handler for the `append_inferences` slice.

Lazy open-on-first-write + batch append. Two-step non-transactional
write per gate-review L1 + L2:

  1. Load Decision via `load_decision` (fold-on-read).
  2. If `decision.logbooks[LOGBOOK_KIND_INFERENCE]` is absent:
     emit `DecisionLogbookOpened` to the Decision stream.
  3. Read the logbook_id (from existing or just-emitted).
  4. Construct `Inference` rows with the logbook_id +
     correlation_id + decision_id from the envelope.
  5. `inference_store.append(rows)`, silent dedup via Postgres PK
     (or InMemory dict setdefault).

## Self-healing on failure

  - Step 1 succeeds, step 2 fails (concurrency on Decision stream):
    handler retries from step 1; the conflicting writer either also
    opened a reasoning logbook (we now see it open on reload, skip
    step 2) OR registered a different event entirely (still safe to
    proceed).
  - Step 2 succeeds, step 5 fails: dangling open logbook with no
    entries. The next call sees the logbook is open, skips step 2,
    and retries the entry append. UUIDv7 PK + at-most-one-open
    invariant make this fully recoverable.

## Why not idempotency-wrapped

Natural idempotence: at-most-one-open invariant catches double-
opens; entry-store PK catches double-appends. Wrapping the slice
in idempotency would add no value beyond what the domain already
guarantees.

## Cross-track surface

Decision (own BC) is loaded. The producer's reasoning entries
typically reference external concepts (model names, tool names,
agent IDs) stored as opaque strings without cross-aggregate
validation, with ONE exception: `agent_id` must equal the calling
principal when set (agent-attributed rows are the budget ledger;
see `InferenceAgentMismatchError`). No Agent aggregate is loaded,
the check is a pure string comparison against the envelope.
"""

from typing import Protocol
from uuid import UUID

from cora.decision.aggregates.decision import (
    INFERENCE_LOGBOOK_SCHEMA,
    LOGBOOK_KIND_INFERENCE,
    DecisionLogbookOpened,
    DecisionNotFoundError,
    Inference,
    InferenceStore,
    event_type_name,
    load_decision,
    to_payload,
)
from cora.decision.errors import InferenceAgentMismatchError, UnauthorizedError
from cora.decision.features.append_inferences.command import (
    AppendInferences,
    ReasoningEntryInput,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Decision"
_COMMAND_NAME = "AppendInferences"
_LAZY_OPEN_MAX_RETRIES = 3
"""Bounded retry count for the lazy-open ConcurrencyError loop.

Each retry re-loads the Decision (so subsequent attempts see any
concurrently-opened logbook + skip the open step). 3 attempts
covers the realistic burst-write window; beyond that we surface
the conflict as a 500 rather than spinning indefinitely."""

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every append_inferences handler implements."""

    async def __call__(
        self,
        command: AppendInferences,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int: ...


def bind(deps: Kernel, *, inference_store: InferenceStore) -> Handler:
    """Build an append_inferences handler closed over deps + store.

    `inference_store` is BC-internal (constructed in `wire_decision`
    from `deps.pool` for Postgres, or InMemory for `app_env=test`).
    Not promoted to Kernel per the per-category-writer pattern
    locked at gate-review L9 (mirrors Conduit's VerdictStore).
    """

    async def handler(
        command: AppendInferences,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        _log.info(
            "append_inferences.start",
            command_name=_COMMAND_NAME,
            decision_id=str(command.decision_id),
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
                "append_inferences.denied",
                command_name=_COMMAND_NAME,
                decision_id=str(command.decision_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=authz.reason,
            )
            raise UnauthorizedError(authz.reason)

        # Agent attribution is principal-bound: entry rows keyed by
        # agent_id are the spend ledger the AgentBudget gate sums, so a
        # producer may only record spend against itself. Reject the
        # whole batch BEFORE any write (no logbook open, no partial
        # append) so a spoofing request leaves no trace to clean up.
        principal_str = str(principal_id)
        for entry in command.entries:
            if entry.agent_id is not None and entry.agent_id != principal_str:
                _log.warning(
                    "append_inferences.agent_mismatch",
                    command_name=_COMMAND_NAME,
                    decision_id=str(command.decision_id),
                    entry_event_id=str(entry.event_id),
                    entry_agent_id=entry.agent_id,
                    principal_id=principal_str,
                    correlation_id=str(correlation_id),
                )
                raise InferenceAgentMismatchError(
                    entry_agent_id=entry.agent_id,
                    principal_id=principal_str,
                )

        # Resolve the reasoning logbook id, opening it lazily on the
        # first append. Retries on ConcurrencyError (a parallel writer
        # incrementing the Decision stream's version between our
        # load + append): the retry re-loads, and either sees the
        # logbook now open (skips the open) or proceeds with a fresh
        # version. Bounded retry, beyond _LAZY_OPEN_MAX_RETRIES the
        # conflict surfaces as 500 rather than infinite spin.
        opened_logbook_now = False
        for attempt in range(_LAZY_OPEN_MAX_RETRIES):
            decision = await load_decision(deps.event_store, command.decision_id)
            if decision is None:
                raise DecisionNotFoundError(command.decision_id)
            existing_logbook_id = decision.logbooks.get(LOGBOOK_KIND_INFERENCE)
            if existing_logbook_id is not None:
                logbook_id = existing_logbook_id
                break
            now = deps.clock.now()
            new_logbook_id = deps.id_generator.new_id()
            open_event = DecisionLogbookOpened(
                decision_id=command.decision_id,
                logbook_id=new_logbook_id,
                kind=LOGBOOK_KIND_INFERENCE,
                schema=INFERENCE_LOGBOOK_SCHEMA,
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
                stream_id=command.decision_id,
            )
            try:
                await deps.event_store.append(
                    stream_type=_STREAM_TYPE,
                    stream_id=command.decision_id,
                    expected_version=current_version,
                    events=[stored_open],
                )
            except ConcurrencyError:
                _log.info(
                    "append_inferences.lazy_open_concurrency_retry",
                    command_name=_COMMAND_NAME,
                    decision_id=str(command.decision_id),
                    attempt=attempt,
                )
                continue
            logbook_id = new_logbook_id
            opened_logbook_now = True
            break
        else:  # pragma: no cover  # retry-exhaustion guard, requires contention injection
            # Hit retry limit; surface the conflict.
            raise ConcurrencyError(
                stream_type=_STREAM_TYPE,
                stream_id=command.decision_id,
                expected=-1,
                actual=-1,
            )

        # Construct Inference rows with the BC-infra fields
        # populated from the URL path + envelope.
        rows = [
            _build_row(entry, command.decision_id, logbook_id, correlation_id, causation_id)
            for entry in command.entries
        ]
        await inference_store.append(rows)

        _log.info(
            "append_inferences.success",
            command_name=_COMMAND_NAME,
            decision_id=str(command.decision_id),
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
    entry: ReasoningEntryInput,
    decision_id: UUID,
    logbook_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None,
) -> Inference:
    """Compose the producer's input plus envelope context into a
    Inference row ready for the store."""
    return Inference(
        event_id=entry.event_id,
        decision_id=decision_id,
        logbook_id=logbook_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=entry.occurred_at,
        duration=entry.duration,
        operation_name=entry.operation_name,
        provider_name=entry.provider_name,
        request_model=entry.request_model,
        response_id=entry.response_id,
        response_model=entry.response_model,
        request_temperature=entry.request_temperature,
        request_top_p=entry.request_top_p,
        request_max_tokens=entry.request_max_tokens,
        output_type=entry.output_type,
        finish_reasons=entry.finish_reasons,
        input_tokens=entry.input_tokens,
        output_tokens=entry.output_tokens,
        cost_usd=entry.cost_usd,
        agent_id=entry.agent_id,
        agent_name=entry.agent_name,
        agent_description=entry.agent_description,
        conversation_id=entry.conversation_id,
        tool_name=entry.tool_name,
        tool_call_id=entry.tool_call_id,
        tool_type=entry.tool_type,
        messages=entry.messages,
    )
