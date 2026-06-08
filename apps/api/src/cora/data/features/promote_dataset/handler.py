"""Application handler for the `promote_dataset` slice.

Update-style handler that loads the Dataset stream PLUS each Dataset
in `state.derived_from` (for the lineage-must-be-Production guard).
Stays longhand for the same reason 6h `add_plan_wire` does: it loads
more than one stream, so it can't share a single-stream factory.

NOT idempotency-wrapped: promotion is strict-not-idempotent at the
decider (re-promote raises DatasetAlreadyPromotedError); apply only
when cached-success-on-retry semantics are needed.

## Pre-load order

  1. Authorize the principal for the `PromoteDataset` command.
  2. Load the Dataset stream and fold to current state.
  3. If `state.derived_from` is non-empty, load each peer Dataset
     into the `DatasetPromotionContext`. Skipped (empty context) when
     state has no derived_from references.
  4. Pass state + context into the pure decider.
  5. Persist the resulting events.

The decider's lineage-integrity guard reads `loaded.intent` for each
peer; the load is required because intent can change over time
(Trial -> Production via this slice, or future demotion paths).
Re-loading at promotion time is the canonical "capture the world
right now, validate, then commit" pattern.

## Missing-peer-load failure mode (gate review documentation)

If `load_dataset` returns None for a peer that's referenced in
`state.derived_from`, the handler silently drops the peer from
`DatasetPromotionContext.derived_from`. The decider then iterates only
the LOADED peers — meaning a peer that vanished from the event
store is NOT flagged. Two reasons this is operationally safe:

  1. The event-store immutability guarantee (REVOKE UPDATE/DELETE
     on the cora_app role) makes "peer vanished from the event
     store" structurally impossible in production.
  2. Pre-7e registration via 7c's existence guard
     (`DerivedFromDatasetsNotFoundError`) prevents creating a
     Dataset whose derived_from references a non-existent stream
     in the first place.

If those guarantees are ever weakened (for example, manual stream deletion
for compliance), the lineage-must-be-Production guard would silently
permit promotion of Datasets whose lineage proof has gone missing.
"""

from typing import Protocol
from uuid import UUID

from cora.data.aggregates.dataset import (
    Dataset,
    DatasetEvent,
    event_type_name,
    fold,
    from_stored,
    load_dataset,
    to_payload,
)
from cora.data.errors import UnauthorizedError
from cora.data.features.promote_dataset.command import PromoteDataset
from cora.data.features.promote_dataset.context import DatasetPromotionContext
from cora.data.features.promote_dataset.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Dataset"
_COMMAND_NAME = "PromoteDataset"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every promote_dataset handler implements."""

    async def __call__(
        self,
        command: PromoteDataset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a promote_dataset handler closed over the shared deps."""

    async def handler(
        command: PromoteDataset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "promote_dataset.start",
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
                "promote_dataset.denied",
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

        # Load peer Datasets for the lineage-must-be-Production guard.
        # Only load when state is non-None AND derived_from is non-empty
        # (avoid unnecessary I/O when the cheap rejections will fire
        # first). The decider checks state-is-None and consults context
        # only after the simpler guards.
        derived_from_loaded: dict[UUID, Dataset] = {}
        if state is not None and state.derived_from:
            for derived_id in sorted(state.derived_from, key=str):
                loaded = await load_dataset(deps.event_store, derived_id)
                if loaded is not None:
                    derived_from_loaded[derived_id] = loaded
                # Missing derived_from refs are not fatal at promotion
                # time: they would have been validated at registration
                # via DerivedFromDatasetsNotFoundError. If a peer was
                # later discarded but kept its event stream (the
                # immutability guarantee preserves all events), it
                # loads cleanly here with status=DISCARDED. The decider
                # rejects discarded peers via the lineage-not-Production
                # guard (Discarded peers have intent=Trial typically,
                # since promotion happens before discard in normal
                # workflows).

        context = DatasetPromotionContext(derived_from=derived_from_loaded)

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
            promoted_by=ActorId(principal_id),
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
            "promote_dataset.success",
            command_name=_COMMAND_NAME,
            dataset_id=str(command.dataset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
