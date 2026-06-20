"""Compose the Recipe BC's handlers from `Kernel`.

`wire_recipe(deps)` is invoked once from the FastAPI lifespan and
the returned `RecipeHandlers` bundle is stored on
`app.state.recipe`. Routes and MCP tools pull their handler out of
that bundle. New slices (commands or queries) add a new field on
`RecipeHandlers` and a single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment (composition order matters — innermost first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing` — OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

The BC owns five aggregates: `Method` (the technique contract),
`Practice` (a Method adaptation), `Plan` (an executable binding of
Practices to Assets), `Capability` (the universal declarative
template Methods and Procedures realize as executors), and `Recipe`
(the deployment-bound templated step sequence that expands to a
flat Step list at register_procedure_from_recipe time).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.recipe.features import (
    add_method_required_role,
    add_plan_wire,
    bind_plan_role,
    define_capability,
    define_method,
    define_plan,
    define_practice,
    define_recipe,
    deprecate_capability,
    deprecate_method,
    deprecate_plan,
    deprecate_practice,
    deprecate_recipe,
    get_capability,
    get_method,
    get_plan,
    get_practice,
    get_recipe,
    inspect_plan_binding,
    list_methods,
    list_plans,
    list_practices,
    remove_method_required_role,
    remove_plan_wire,
    unbind_plan_role,
    update_capability_suggested_roles,
    update_method_launch_spec,
    update_method_parameters_schema,
    update_plan_default_parameters,
    version_capability,
    version_method,
    version_plan,
    version_practice,
    version_recipe,
)

_BC = "recipe"


@dataclass(frozen=True)
class RecipeHandlers:
    """The Recipe BC's handler bundle, each closed over Kernel."""

    define_method: define_method.IdempotentHandler
    get_method: get_method.Handler
    version_method: version_method.Handler
    deprecate_method: deprecate_method.Handler
    update_method_parameters_schema: update_method_parameters_schema.Handler
    update_method_launch_spec: update_method_launch_spec.Handler
    add_method_required_role: add_method_required_role.Handler
    remove_method_required_role: remove_method_required_role.Handler
    define_practice: define_practice.IdempotentHandler
    get_practice: get_practice.Handler
    version_practice: version_practice.Handler
    deprecate_practice: deprecate_practice.Handler
    define_plan: define_plan.IdempotentHandler
    get_plan: get_plan.Handler
    version_plan: version_plan.Handler
    deprecate_plan: deprecate_plan.Handler
    update_plan_default_parameters: update_plan_default_parameters.Handler
    add_plan_wire: add_plan_wire.Handler
    remove_plan_wire: remove_plan_wire.Handler
    bind_plan_role: bind_plan_role.Handler
    unbind_plan_role: unbind_plan_role.Handler
    list_methods: list_methods.Handler
    list_practices: list_practices.Handler
    list_plans: list_plans.Handler
    define_capability: define_capability.IdempotentHandler
    version_capability: version_capability.Handler
    deprecate_capability: deprecate_capability.Handler
    update_capability_suggested_roles: update_capability_suggested_roles.Handler
    get_capability: get_capability.Handler
    define_recipe: define_recipe.IdempotentHandler
    version_recipe: version_recipe.Handler
    deprecate_recipe: deprecate_recipe.Handler
    get_recipe: get_recipe.Handler
    inspect_plan_binding: inspect_plan_binding.Handler


def wire_recipe(deps: Kernel) -> RecipeHandlers:
    """Build the Recipe BC handlers from shared dependencies."""
    return RecipeHandlers(
        define_method=with_tracing(
            with_idempotency(
                define_method.bind(deps),
                deps.idempotency_store,
                command_name="DefineMethod",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineMethod",
            bc=_BC,
        ),
        get_method=with_tracing(
            get_method.bind(deps),
            command_name="GetMethod",
            bc=_BC,
            kind="query",
        ),
        version_method=with_tracing(
            version_method.bind(deps),
            command_name="VersionMethod",
            bc=_BC,
        ),
        deprecate_method=with_tracing(
            deprecate_method.bind(deps),
            command_name="DeprecateMethod",
            bc=_BC,
        ),
        update_method_parameters_schema=with_tracing(
            update_method_parameters_schema.bind(deps),
            command_name="UpdateMethodParametersSchema",
            bc=_BC,
        ),
        update_method_launch_spec=with_tracing(
            update_method_launch_spec.bind(deps),
            command_name="UpdateMethodLaunchSpec",
            bc=_BC,
        ),
        add_method_required_role=with_tracing(
            add_method_required_role.bind(deps),
            command_name="AddMethodRequiredRole",
            bc=_BC,
        ),
        remove_method_required_role=with_tracing(
            remove_method_required_role.bind(deps),
            command_name="RemoveMethodRequiredRole",
            bc=_BC,
        ),
        define_practice=with_tracing(
            with_idempotency(
                define_practice.bind(deps),
                deps.idempotency_store,
                command_name="DefinePractice",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefinePractice",
            bc=_BC,
        ),
        get_practice=with_tracing(
            get_practice.bind(deps),
            command_name="GetPractice",
            bc=_BC,
            kind="query",
        ),
        version_practice=with_tracing(
            version_practice.bind(deps),
            command_name="VersionPractice",
            bc=_BC,
        ),
        deprecate_practice=with_tracing(
            deprecate_practice.bind(deps),
            command_name="DeprecatePractice",
            bc=_BC,
        ),
        define_plan=with_tracing(
            with_idempotency(
                define_plan.bind(deps),
                deps.idempotency_store,
                command_name="DefinePlan",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefinePlan",
            bc=_BC,
        ),
        get_plan=with_tracing(
            get_plan.bind(deps),
            command_name="GetPlan",
            bc=_BC,
            kind="query",
        ),
        version_plan=with_tracing(
            version_plan.bind(deps),
            command_name="VersionPlan",
            bc=_BC,
        ),
        deprecate_plan=with_tracing(
            deprecate_plan.bind(deps),
            command_name="DeprecatePlan",
            bc=_BC,
        ),
        update_plan_default_parameters=with_tracing(
            update_plan_default_parameters.bind(deps),
            command_name="UpdatePlanDefaultParameters",
            bc=_BC,
        ),
        add_plan_wire=with_tracing(
            add_plan_wire.bind(deps),
            command_name="AddPlanWire",
            bc=_BC,
        ),
        remove_plan_wire=with_tracing(
            remove_plan_wire.bind(deps),
            command_name="RemovePlanWire",
            bc=_BC,
        ),
        bind_plan_role=with_tracing(
            bind_plan_role.bind(deps),
            command_name="BindPlanRole",
            bc=_BC,
        ),
        unbind_plan_role=with_tracing(
            unbind_plan_role.bind(deps),
            command_name="UnbindPlanRole",
            bc=_BC,
        ),
        list_methods=with_tracing(
            list_methods.bind(deps),
            command_name="ListMethods",
            bc=_BC,
            kind="query",
        ),
        list_practices=with_tracing(
            list_practices.bind(deps),
            command_name="ListPractices",
            bc=_BC,
            kind="query",
        ),
        list_plans=with_tracing(
            list_plans.bind(deps),
            command_name="ListPlans",
            bc=_BC,
            kind="query",
        ),
        define_capability=with_tracing(
            with_idempotency(
                define_capability.bind(deps),
                deps.idempotency_store,
                command_name="DefineCapability",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineCapability",
            bc=_BC,
        ),
        version_capability=with_tracing(
            version_capability.bind(deps),
            command_name="VersionCapability",
            bc=_BC,
        ),
        deprecate_capability=with_tracing(
            deprecate_capability.bind(deps),
            command_name="DeprecateCapability",
            bc=_BC,
        ),
        update_capability_suggested_roles=with_tracing(
            update_capability_suggested_roles.bind(deps),
            command_name="UpdateCapabilitySuggestedRoles",
            bc=_BC,
        ),
        get_capability=with_tracing(
            get_capability.bind(deps),
            command_name="GetCapability",
            bc=_BC,
            kind="query",
        ),
        define_recipe=with_tracing(
            with_idempotency(
                define_recipe.bind(deps),
                deps.idempotency_store,
                command_name="DefineRecipe",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineRecipe",
            bc=_BC,
        ),
        version_recipe=with_tracing(
            version_recipe.bind(deps),
            command_name="VersionRecipe",
            bc=_BC,
        ),
        deprecate_recipe=with_tracing(
            deprecate_recipe.bind(deps),
            command_name="DeprecateRecipe",
            bc=_BC,
        ),
        get_recipe=with_tracing(
            get_recipe.bind(deps),
            command_name="GetRecipe",
            bc=_BC,
            kind="query",
        ),
        inspect_plan_binding=with_tracing(
            inspect_plan_binding.bind(deps),
            command_name="InspectPlanBinding",
            bc=_BC,
            kind="query",
        ),
    )
