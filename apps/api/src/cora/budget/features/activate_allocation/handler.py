"""Application handler for the `activate_allocation` slice.

Longhand, not factory-built, for the same reason `seal_allocation` is:
it consults a CROSS-stream fact between authorize and append that no
single-stream update factory expresses. Activation opens the
deployment's one instrument spend window, so before it fires the
handler asks `allocation_lookup.find_active()` and refuses with
`AllocationAlreadyActiveError` if a DIFFERENT envelope is already
Active. That makes the single-Active invariant the gates and the
sealer rely on best-effort true: without it, activating a second
envelope would silently stop enforcing the first's ceiling and orphan
its automatic seal.

The check reads the summary projection, so a tight concurrent
activate race is possible and accepted; the invariant is a guard, not
a lock. The fold still records `(activated_at, activated_by)` per
[[project_fold_symmetry_design]], so the handler threads the
envelope's `principal_id` into the decider as `activated_by`.
"""

from typing import Protocol
from uuid import UUID

from cora.budget.aggregates.allocation import (
    AllocationAlreadyActiveError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.budget.errors import UnauthorizedError
from cora.budget.features.activate_allocation.command import ActivateAllocation
from cora.budget.features.activate_allocation.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Allocation"
_COMMAND_NAME = "ActivateAllocation"

_log = get_logger("activate_allocation")


class Handler(Protocol):
    """Callable interface every activate_allocation handler implements."""

    async def __call__(
        self,
        command: ActivateAllocation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an activate_allocation handler closed over the shared deps."""

    async def handler(
        command: ActivateAllocation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        allocation_id = command.allocation_id
        _log.info(
            "activate_allocation.start",
            command_name=_COMMAND_NAME,
            allocation_id=str(allocation_id),
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
                "activate_allocation.denied",
                command_name=_COMMAND_NAME,
                allocation_id=str(allocation_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        active = await deps.allocation_lookup.find_active()
        if active is not None and active.allocation_id != allocation_id:
            _log.info(
                "activate_allocation.already_active",
                command_name=_COMMAND_NAME,
                allocation_id=str(allocation_id),
                active_allocation_id=str(active.allocation_id),
                correlation_id=str(correlation_id),
            )
            raise AllocationAlreadyActiveError(allocation_id, active.allocation_id)

        now = deps.clock.now()
        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=allocation_id,
        )
        state = fold([from_stored(s) for s in stored])

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            activated_by=ActorId(principal_id),
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
            stream_id=allocation_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "activate_allocation.success",
            command_name=_COMMAND_NAME,
            allocation_id=str(allocation_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
