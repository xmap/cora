"""Application handler for `update_capability_suggested_roles`.

Update-style handler: load Capability + edge-load each role_id in the
command's `suggested_role_ids` via `Kernel.role_lookup.lookup`
(parallel batch via `asyncio.gather`) + decide + append.

Per memo critique B1 (3E): role existence validates by edge-loading
each id through the RoleLookup port rather than introducing a
`RoleLookup.batch_lookup` method -- keeps RoleLookup narrow at single
`lookup()`. None-resolving role_ids surface as RoleNotFoundError at
the handler edge so callers see a 404 rather than a satisfaction-side
mis-record.

Documentation-only event per memo Lock 10: no fitness gates on the
set membership itself.
"""

import asyncio
from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.role import RoleNotFoundError
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.capability import (
    CapabilityEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.update_capability_suggested_roles.command import (
    UpdateCapabilitySuggestedRoles,
)
from cora.recipe.features.update_capability_suggested_roles.decider import decide

_STREAM_TYPE = "Capability"
_COMMAND_NAME = "UpdateCapabilitySuggestedRoles"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every update_capability_suggested_roles handler implements."""

    async def __call__(
        self,
        command: UpdateCapabilitySuggestedRoles,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_capability_suggested_roles handler closed over deps."""

    async def handler(
        command: UpdateCapabilitySuggestedRoles,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "update_capability_suggested_roles.start",
            command_name=_COMMAND_NAME,
            capability_id=str(command.capability_id),
            suggested_role_ids_count=len(command.suggested_role_ids),
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
                "update_capability_suggested_roles.denied",
                command_name=_COMMAND_NAME,
                capability_id=str(command.capability_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Edge-load: resolve every role_id via RoleLookup (concurrent
        # via asyncio.gather; cheap when the set is small, which is
        # the operational case for editorial set authoring). The
        # first missing role surfaces as RoleNotFoundError.
        results = await asyncio.gather(
            *(deps.role_lookup.lookup(rid) for rid in command.suggested_role_ids)
        )
        for rid, row in zip(command.suggested_role_ids, results, strict=True):
            if row is None:
                raise RoleNotFoundError(rid)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.capability_id,
        )
        history: list[CapabilityEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide(state=state, command=command, now=now)

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
            stream_id=command.capability_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "update_capability_suggested_roles.success",
            command_name=_COMMAND_NAME,
            capability_id=str(command.capability_id),
            suggested_role_ids_count=len(command.suggested_role_ids),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
