"""Application handler for the `discard_dataset` slice.

Update-style handler: load existing Dataset stream, fold to current
state, run pure decider, append the resulting events with optimistic
concurrency. Same shape as discard_subject (no idempotency wrap;
the strict-not-idempotent decider provides the natural retry-safety
through DatasetCannotDiscardError on the second attempt).
"""

from typing import Protocol
from uuid import UUID

from cora.data.aggregates.dataset import (
    DatasetEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.data.errors import UnauthorizedError
from cora.data.features.discard_dataset.command import DiscardDataset
from cora.data.features.discard_dataset.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Dataset"
_COMMAND_NAME = "DiscardDataset"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every discard_dataset handler implements."""

    async def __call__(
        self,
        command: DiscardDataset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a discard_dataset handler closed over the shared deps."""

    async def handler(
        command: DiscardDataset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "discard_dataset.start",
            command_name=_COMMAND_NAME,
            dataset_id=str(command.dataset_id),
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
                "discard_dataset.denied",
                command_name=_COMMAND_NAME,
                dataset_id=str(command.dataset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.dataset_id,
        )
        history: list[DatasetEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide(
            state=state, command=command, now=now, discarded_by=ActorId(principal_id)
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
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.dataset_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "discard_dataset.success",
            command_name=_COMMAND_NAME,
            dataset_id=str(command.dataset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
