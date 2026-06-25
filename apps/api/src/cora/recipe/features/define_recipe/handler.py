"""Application handler for the `define_recipe` slice.

Create-style handler with a cross-aggregate fan-out preceding the
decider call: loads the referenced Capability via
`load_capability(deps.event_store, ...)`, then validates the
supplied steps' BindingRef integrity against
`Capability.parameters_schema.properties`. The handler raises the
existing `CapabilityNotFoundError` cross-aggregate when the
Capability stream is empty (anti-hook 18 of
[[project-recipe-aggregate-design]]: do NOT invent a new
error class for missing-Capability).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.capability import (
    CapabilityNotFoundError,
    load_capability,
)
from cora.recipe.aggregates.recipe import (
    event_type_name,
    to_payload,
    validate_capture_refs,
    validate_output_refs,
    validate_recipe_steps_against_capability_schema,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.define_recipe.command import DefineRecipe
from cora.recipe.features.define_recipe.decider import decide

_STREAM_TYPE = "Recipe"
_COMMAND_NAME = "DefineRecipe"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_recipe handler, the shape `bind()` returns."""

    async def __call__(
        self,
        command: DefineRecipe,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_recipe handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefineRecipe,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a define_recipe handler closed over the shared deps."""

    async def handler(
        command: DefineRecipe,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "define_recipe.start",
            command_name=_COMMAND_NAME,
            capability_id=str(command.capability_id),
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
                "define_recipe.denied",
                command_name=_COMMAND_NAME,
                capability_id=str(command.capability_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        capability = await load_capability(deps.event_store, command.capability_id)
        if capability is None:
            raise CapabilityNotFoundError(command.capability_id)
        validate_recipe_steps_against_capability_schema(command.steps, capability.parameters_schema)
        validate_capture_refs(command.steps)
        validate_output_refs(command.steps)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
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
            "define_recipe.success",
            command_name=_COMMAND_NAME,
            recipe_id=str(new_id),
            capability_id=str(command.capability_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
