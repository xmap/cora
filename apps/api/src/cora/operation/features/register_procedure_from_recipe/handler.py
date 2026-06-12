"""Application handler for the `register_procedure_from_recipe` slice.

Create-style handler with TWO cross-aggregate fan-out steps preceding
the decider call:

  1. Load Recipe via `load_recipe(deps.event_store, command.recipe_id)`.
     Missing -> `RecipeNotFoundError` (re-used cross-BC; mapped to 404).
  2. Load Capability via `load_capability(deps.event_store,
     recipe.capability_id)`. Missing -> `CapabilityNotFoundError`
     (re-used cross-BC per anti-hook 18 of
     [[project-recipe-aggregate-design]]: do NOT invent a new error
     class for missing-Capability).
  3. Re-validate BindingRef integrity against the CURRENT
     `Capability.parameters_schema` (closes the Capability-re-version
     race per anti-hook 5). Drift -> `RecipeBindingsStaleAgainstCurrentCapabilityError`.

The handler then invokes the decider with both `recipe` and
`capability` in scope; the decider runs the executor-shape guard,
binding-value shape validation, overflow + determinism gates, and
emits `[ProcedureRegistered, RecipeExpansionRecorded]`.

Receives a `RecipeExpander` from `bind()`'s captured deps so the
decider can run the cap + determinism gates without re-importing
infrastructure inside the pure layer.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.aggregates.procedure import (
    RecipeBindingsStaleAgainstCurrentCapabilityError,
    event_type_name,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.register_procedure_from_recipe.command import (
    RegisterProcedureFromRecipe,
)
from cora.operation.features.register_procedure_from_recipe.decider import decide
from cora.operation.ports.recipe_expander import RecipeExpander
from cora.recipe.aggregates.capability import (
    CapabilityNotFoundError,
    load_capability,
)
from cora.recipe.aggregates.recipe import (
    RecipeNotFoundError,
    collect_binding_names,
    load_recipe,
)

_STREAM_TYPE = "Procedure"
_COMMAND_NAME = "RegisterProcedureFromRecipe"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_procedure_from_recipe handler, the shape `bind()` returns."""

    async def __call__(
        self,
        command: RegisterProcedureFromRecipe,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_procedure_from_recipe handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterProcedureFromRecipe,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel, *, expansion_port: RecipeExpander) -> Handler:
    """Build a register_procedure_from_recipe handler closed over deps + port."""

    async def handler(
        command: RegisterProcedureFromRecipe,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_procedure_from_recipe.start",
            command_name=_COMMAND_NAME,
            recipe_id=str(command.recipe_id),
            kind=command.kind,
            target_asset_count=len(command.target_asset_ids),
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
                "register_procedure_from_recipe.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        recipe = await load_recipe(deps.event_store, command.recipe_id)
        if recipe is None:
            raise RecipeNotFoundError(command.recipe_id)

        capability = await load_capability(deps.event_store, recipe.capability_id)
        if capability is None:
            raise CapabilityNotFoundError(recipe.capability_id)

        # Re-validate BindingRef integrity against the CURRENT
        # Capability.parameters_schema. If the Capability has been
        # versioned after the Recipe was last written and a binding
        # name dropped, raise RecipeBindingsStaleAgainstCurrentCapabilityError
        # so the operator re-versions the Recipe.
        binding_names = collect_binding_names(recipe.steps)
        declared: frozenset[str] = frozenset()
        if capability.parameters_schema is not None:
            raw_properties: object = capability.parameters_schema.get("properties", {})
            if isinstance(raw_properties, dict):
                # `properties` is dict[str, Any] in JSON Schema; the key
                # type is enforced by the validator at write time. Cast
                # the keys view explicitly so pyright sees `Iterable[str]`.
                declared = frozenset(
                    str(k)  # pyright: ignore[reportUnknownArgumentType]
                    for k in raw_properties  # pyright: ignore[reportUnknownVariableType]
                )
        missing = binding_names - declared
        if missing:
            raise RecipeBindingsStaleAgainstCurrentCapabilityError(
                recipe_id=recipe.id,
                capability_id=capability.id,
                missing_binding_names=missing,
            )

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            recipe=recipe,
            capability=capability,
            expansion_port=expansion_port,
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
            "register_procedure_from_recipe.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(new_id),
            recipe_id=str(command.recipe_id),
            capability_id=str(recipe.capability_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
