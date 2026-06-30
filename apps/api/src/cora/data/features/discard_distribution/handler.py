"""Application handler for the `discard_distribution` slice.

Update-style handler: load the existing Distribution stream to current
state + version, pre-load the parent Dataset (parent-Discarded guard)
and the sibling copies (the redundancy guard), run the pure decider,
append the resulting event with optimistic concurrency. Bare handler,
no idempotency wrap; the strict-not-idempotent decider provides the
natural retry-safety through DistributionCannotDiscardError on the
second attempt.

## Pre-load order

  1. `load_distribution(distribution_id)` -> if None,
     `DistributionNotFoundError` (Data BC NotFoundError -> 404). Returns
     the current version for the optimistic-concurrency append.
  2. `load_dataset(distribution.dataset_id)` -> if None,
     `DatasetNotFoundError`. The parent must exist; the decider reads its
     status for the parent-Discarded guard.
  3. `dataset_distribution_lookup.find_by_datasets({dataset_id})` -> the
     sibling set (non-Discarded copies of the same Dataset, projection-
     backed). The decider reads the Verified-on-a-different-tier
     redundancy signal off it.

The sibling read is projection-derived (eventual); see the decider
docstring for the accepted two-concurrent-discards race and the
deferred parent-Dataset-stream CAS.
"""

from typing import Protocol
from uuid import UUID

from cora.data.aggregates.dataset import (
    DatasetNotFoundError,
    load_dataset,
)
from cora.data.aggregates.distribution import (
    DistributionEvent,
    DistributionNotFoundError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.data.errors import UnauthorizedError
from cora.data.features.discard_distribution.command import DiscardDistribution
from cora.data.features.discard_distribution.context import DiscardDistributionContext
from cora.data.features.discard_distribution.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Distribution"
_COMMAND_NAME = "DiscardDistribution"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every discard_distribution handler implements."""

    async def __call__(
        self,
        command: DiscardDistribution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a discard_distribution handler closed over the shared deps."""

    async def handler(
        command: DiscardDistribution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "discard_distribution.start",
            command_name=_COMMAND_NAME,
            distribution_id=str(command.distribution_id),
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
                "discard_distribution.denied",
                command_name=_COMMAND_NAME,
                distribution_id=str(command.distribution_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.distribution_id,
        )
        history: list[DistributionEvent] = [from_stored(s) for s in stored]
        state = fold(history)
        if state is None:
            raise DistributionNotFoundError(command.distribution_id)

        dataset = await load_dataset(deps.event_store, state.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(state.dataset_id)

        siblings_by_dataset = await deps.dataset_distribution_lookup.find_by_datasets(
            frozenset({state.dataset_id})
        )
        sibling_distributions = siblings_by_dataset.get(state.dataset_id, ())

        context = DiscardDistributionContext(
            dataset=dataset,
            sibling_distributions=sibling_distributions,
        )

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
            discarded_by=ActorId(principal_id),
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
            stream_id=command.distribution_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "discard_distribution.success",
            command_name=_COMMAND_NAME,
            distribution_id=str(command.distribution_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
