"""Application handler for the `deprecate_model` slice.

Update-style handler shape: load + fold + decide + append. Mirrors
the version_model precedent for Model-aggregate transitions and the
deprecate_family precedent for the deprecation command shape.

Not idempotency-wrapped: domain-idempotent via
`ModelCannotDeprecateError` on retry from `Deprecated` (matches the
deprecate_family stance). The reason field is treated as authoring
intent; a fresh attempt against an already-Deprecated Model is a
real conflict the operator should see, not a silent no-op.

NO cross-BC lookup here: deprecation is an authoring signal on the
Model stream itself. Existing Assets bound to this Model continue
to function; the runtime gate is elsewhere.
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
from cora.equipment.features.deprecate_model.command import DeprecateModel
from cora.equipment.features.deprecate_model.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Model"
_COMMAND_NAME = "DeprecateModel"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every deprecate_model handler implements."""

    async def __call__(
        self,
        command: DeprecateModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a deprecate_model handler closed over the shared deps."""

    async def handler(
        command: DeprecateModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "deprecate_model.start",
            command_name=_COMMAND_NAME,
            model_id=str(command.model_id),
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
                "deprecate_model.denied",
                command_name=_COMMAND_NAME,
                model_id=str(command.model_id),
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
            "deprecate_model.success",
            command_name=_COMMAND_NAME,
            model_id=str(command.model_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
