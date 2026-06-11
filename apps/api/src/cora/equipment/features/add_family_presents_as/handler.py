"""Application handler for the `add_family_presents_as` slice.

Update-style handler shape -- load Family stream + load RoleLookup
at the edge + decide + append. Not idempotency-wrapped (domain-
idempotent via `FamilyRolePresentsAsAlreadyError` on retry; same
precedent as add_asset_family / Asset lifecycle transitions).

Stays longhand (does not use any factory): the command carries
`role_id` in addition to `family_id`, and the handler logs
`role_id` at start + success for diagnostic visibility. Same
justification as `add_asset_family`.

The RoleLookup check lives in the HANDLER (not the decider) so the
decider stays pure + dependency-free. Decider receives the
resolved `RoleLookupResult` and performs the affordance-superset
check synchronously.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.family import (
    FamilyEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.role import RoleNotFoundError
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.add_family_presents_as.command import AddFamilyPresentsAs
from cora.equipment.features.add_family_presents_as.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Family"
_COMMAND_NAME = "AddFamilyPresentsAs"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every add_family_presents_as handler implements."""

    async def __call__(
        self,
        command: AddFamilyPresentsAs,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an add_family_presents_as handler closed over the shared deps."""

    async def handler(
        command: AddFamilyPresentsAs,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "add_family_presents_as.start",
            command_name=_COMMAND_NAME,
            family_id=str(command.family_id),
            role_id=str(command.role_id),
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
                "add_family_presents_as.denied",
                command_name=_COMMAND_NAME,
                family_id=str(command.family_id),
                role_id=str(command.role_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Edge-load: resolve the Role via the read-side projection
        # port. None -> RoleNotFoundError translates to 404 at the
        # HTTP boundary. Lives at the handler so the decider stays
        # pure.
        role_lookup_result = await deps.role_lookup.lookup(command.role_id)
        if role_lookup_result is None:
            raise RoleNotFoundError(command.role_id)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.family_id,
        )
        history: list[FamilyEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            role_lookup_result=role_lookup_result,
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
            stream_id=command.family_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "add_family_presents_as.success",
            command_name=_COMMAND_NAME,
            family_id=str(command.family_id),
            role_id=str(command.role_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
