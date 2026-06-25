"""Application handler for the `version_recipe` slice.

Update-style handler shape: load Recipe stream + fold, load the
referenced Capability cross-aggregate, re-validate BindingRef
integrity against the CURRENT Capability.parameters_schema, then
decide + append. NOT idempotency-wrapped: re-versioning emits a
duplicate event per `version_capability` / `version_method`
precedent (re-attestation is the audit signal).

The cross-aggregate re-validation closes the operator-side half of
the Capability-re-version race per anti-hook 5 of
[[project-recipe-aggregate-design]]: if the Capability has been
versioned after the Recipe's last write and a binding name dropped,
this slice rejects with `RecipeBindingReferencesUnknownParameterError`
or `RecipeRequiresCapabilityParametersSchemaError`.
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
    RecipeEvent,
    RecipeNotFoundError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
    validate_capture_refs,
    validate_output_refs,
    validate_recipe_steps_against_capability_schema,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.version_recipe.command import VersionRecipe
from cora.recipe.features.version_recipe.decider import decide

_STREAM_TYPE = "Recipe"
_COMMAND_NAME = "VersionRecipe"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every version_recipe handler implements."""

    async def __call__(
        self,
        command: VersionRecipe,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a version_recipe handler closed over the shared deps."""

    async def handler(
        command: VersionRecipe,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "version_recipe.start",
            command_name=_COMMAND_NAME,
            recipe_id=str(command.recipe_id),
            version_tag=command.version_tag,
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
                "version_recipe.denied",
                command_name=_COMMAND_NAME,
                recipe_id=str(command.recipe_id),
                version_tag=command.version_tag,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.recipe_id,
        )
        history: list[RecipeEvent] = [from_stored(s) for s in stored]
        state = fold(history)
        if state is None:
            raise RecipeNotFoundError(command.recipe_id)

        capability = await load_capability(deps.event_store, state.capability_id)
        if capability is None:
            raise CapabilityNotFoundError(state.capability_id)
        validate_recipe_steps_against_capability_schema(command.steps, capability.parameters_schema)
        validate_capture_refs(command.steps)
        validate_output_refs(command.steps)

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
            stream_id=command.recipe_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "version_recipe.success",
            command_name=_COMMAND_NAME,
            recipe_id=str(command.recipe_id),
            version_tag=command.version_tag,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
