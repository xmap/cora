"""Application handler for the `grant_allocation` slice.

Single-stream genesis on the budget BC's Allocation stream type. No
cross-BC co-write: `campaign_id` is a bare reference (nothing about
an envelope belongs on the Campaign stream), and the envelope's
holder is implicitly the deployment itself at v1.

One deviation from the simple create-style template, mirroring
`define_language_model`: the command may carry a caller-supplied
`allocation_id` (deployments standing envelopes up from configuration
need stable ids across environments). The handler therefore loads the
target stream BEFORE deciding so the decider's genesis guard rejects
an id collision with `AllocationAlreadyExistsError`; the
`expected_version=0` append backstops the race where two callers
grant the same id concurrently. When the command carries None the
handler mints a UUIDv7 via the IdGenerator port.

The handler threads `granted_by=ActorId(principal_id)` into the
decider so the genesis fact-act folds with its attribution half per
[[project_fold_symmetry_design]].

Idempotency-wrappable per the create-style convention; the
`with_idempotency` wrap is applied at `wire.py`, not here.

`causation_id` is the id of the event/message that triggered this
command (None for HTTP / MCP root calls).
"""

from typing import Protocol
from uuid import UUID

from cora.budget.aggregates.allocation import (
    event_type_name,
    load_allocation,
    to_payload,
)
from cora.budget.errors import UnauthorizedError
from cora.budget.features.grant_allocation.command import GrantAllocation
from cora.budget.features.grant_allocation.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Allocation"
_COMMAND_NAME = "GrantAllocation"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare grant_allocation handler -- what `bind()` returns.

    Returns the new envelope's UUID (caller-supplied when the command
    carried one, handler-minted otherwise). Has no idempotency_key
    kwarg; `with_idempotency` at wire.py adds it.
    """

    async def __call__(
        self,
        command: GrantAllocation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """grant_allocation handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: GrantAllocation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a grant_allocation handler closed over the shared deps."""

    async def handler(
        command: GrantAllocation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "grant_allocation.start",
            command_name=_COMMAND_NAME,
            ceiling_usd=command.ceiling_usd,
            campaign_id=str(command.campaign_id) if command.campaign_id is not None else None,
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
                "grant_allocation.denied",
                command_name=_COMMAND_NAME,
                ceiling_usd=command.ceiling_usd,
                campaign_id=str(command.campaign_id) if command.campaign_id is not None else None,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = (
            command.allocation_id
            if command.allocation_id is not None
            else deps.id_generator.new_id()
        )
        now = deps.clock.now()

        # Load the target stream so a caller-supplied id that already
        # has events trips the decider's genesis guard (a handler-minted
        # UUIDv7 folds to None here).
        state = await load_allocation(deps.event_store, new_id)

        domain_events = decide(
            state=state,
            command=command,
            now=now,
            new_id=new_id,
            granted_by=ActorId(principal_id),
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
            "grant_allocation.success",
            command_name=_COMMAND_NAME,
            allocation_id=str(new_id),
            ceiling_usd=command.ceiling_usd,
            campaign_id=str(command.campaign_id) if command.campaign_id is not None else None,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
