"""Application handler for the `remove_model_family` slice.

Update-style handler shape: load + fold + decide + append. Mirrors
the `add_model_family` precedent for the stream load + fold + decide
+ append spine, minus the cross-BC Family lookup: removal only needs
`family_id` to be present in the Model's `declared_families`, and it
proceeds even if the referenced Family has since been
deprecated or deleted from the Family registry.

Not idempotency-wrapped: domain-strict via
`ModelFamilyNotPresentError` on retry (mirrors
`remove_asset_family`).
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.model import (
    ModelEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.remove_model_family.command import RemoveModelFamily
from cora.equipment.features.remove_model_family.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Model"
_COMMAND_NAME = "RemoveModelFamily"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every remove_model_family handler implements."""

    async def __call__(
        self,
        command: RemoveModelFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a remove_model_family handler closed over the shared deps."""

    async def handler(
        command: RemoveModelFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "remove_model_family.start",
            command_name=_COMMAND_NAME,
            model_id=str(command.model_id),
            family_id=str(command.family_id),
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
                "remove_model_family.denied",
                command_name=_COMMAND_NAME,
                model_id=str(command.model_id),
                family_id=str(command.family_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.model_id,
        )
        history: list[ModelEvent] = [from_stored(s) for s in stored]
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
            stream_id=command.model_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "remove_model_family.success",
            command_name=_COMMAND_NAME,
            model_id=str(command.model_id),
            family_id=str(command.family_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
