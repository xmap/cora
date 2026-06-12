"""Application handler for the `register_distribution` slice.

Genesis-style create handler mirroring `register_dataset` shape.
Pre-loads two cross-aggregate refs (parent Dataset + cross-BC
Supply) before invoking the pure decider; both refs are required
context inputs to the decider per L15 + L17.

## Pre-load order

  1. `load_dataset(command.dataset_id)` -> if None,
     `DatasetNotFoundError` (Data BC NotFoundError -> 404).
  2. `SupplyLookup.lookup(command.supply_id)` -> if None,
     `DistributionSupplyNotFoundError` (NEW Data-BC NotFoundError
     -> 404).

No `load_distribution(new_id)`: `new_id` is a freshly-allocated
UUIDv7 so the Distribution stream is guaranteed empty; the
decider is invoked with `state=None`, and the same-stream-id
race at append time is caught by Postgres `ConcurrencyError`
per L29.

Loads run sequentially; could be optimized via asyncio.gather
later if profiling demands.

## Cross-BC port

`deps.supply_lookup.lookup(supply_id)` returns a
`SupplyLookupResult | None` (per L14 + L28). The lookup returns rows
in EVERY status (Available, Degraded, Unavailable, Recovering,
Decommissioned); the decider's only Supply-side gate is `kind ==
"Storage"`, so a Distribution can legitimately be registered
against a Decommissioned Supply for archival completeness.

## Cross-BC import convention

Per [[project-data-distribution-design]] L13 + W13 + P2.5: the
SupplyLookup port lives at `cora.infrastructure.ports`; this
handler does NOT import `cora.supply.*` directly. The cross-BC
reach is `cora.data -> cora.infrastructure.ports.supply_lookup`.
"""

from typing import Protocol
from uuid import UUID

from cora.data.aggregates.dataset import (
    DatasetNotFoundError,
    load_dataset,
)
from cora.data.aggregates.distribution import (
    DistributionSupplyNotFoundError,
    event_type_name,
    to_payload,
)
from cora.data.errors import UnauthorizedError
from cora.data.features.register_distribution.command import RegisterDistribution
from cora.data.features.register_distribution.context import (
    DistributionRegistrationContext,
)
from cora.data.features.register_distribution.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Distribution"
_COMMAND_NAME = "RegisterDistribution"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_distribution handler, what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use
    bare Handler directly when they don't need idempotency
    semantics.
    """

    async def __call__(
        self,
        command: RegisterDistribution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_distribution handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterDistribution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_distribution handler closed over the shared deps."""

    async def handler(
        command: RegisterDistribution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_distribution.start",
            command_name=_COMMAND_NAME,
            dataset_id=str(command.dataset_id),
            supply_id=str(command.supply_id),
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
                "register_distribution.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Pre-load parent Dataset (same-BC).
        dataset = await load_dataset(deps.event_store, command.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(command.dataset_id)

        # Pre-load Supply reference (cross-BC via SupplyLookup port).
        supply = await deps.supply_lookup.lookup(command.supply_id)
        if supply is None:
            raise DistributionSupplyNotFoundError(command.supply_id)

        context = DistributionRegistrationContext(dataset=dataset, supply=supply)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        # No load_distribution; new_id was just generated by
        # deps.id_generator so the stream is guaranteed empty.
        # Append-time expected_version=0 catches any same-stream-id race.
        domain_events = decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=new_id,
            registered_by=ActorId(principal_id),
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
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "register_distribution.success",
            command_name=_COMMAND_NAME,
            distribution_id=str(new_id),
            dataset_id=str(command.dataset_id),
            supply_id=str(command.supply_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
