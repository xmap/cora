"""HTTP setup for the Recipe BC.

`register_recipe_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Recipe
does not re-register them.

## Loop-collapse pattern

Mirrors Equipment / Subject. Generic error handlers per family,
tuple loops to register them. New aggregates and transition errors
append entries without restructuring.

  - 400 (validation): InvalidMethodNameError, InvalidMethodParametersSchemaError,
    InvalidMethodNeededSuppliesError
  - 404 (load miss): MethodNotFoundError
  - 409 (defensive guard for AlreadyExists): MethodAlreadyExistsError
  - 409 (transition guards): future <Aggregate>Cannot<Verb>Error families
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.recipe.aggregates.capability import (
    CapabilityAlreadyExistsError,
    CapabilityCannotDeprecateError,
    CapabilityCannotVersionError,
    CapabilityNotFoundError,
    InvalidCapabilityCodeError,
    InvalidCapabilityDescriptionError,
    InvalidCapabilityNameError,
    InvalidCapabilityParametersSchemaError,
    InvalidCapabilityVersionTagError,
    InvalidExecutorShapesError,
)
from cora.recipe.aggregates.method import (
    InvalidMethodNameError,
    InvalidMethodNeededSuppliesError,
    InvalidMethodParametersSchemaError,
    InvalidMethodVersionTagError,
    MethodAlreadyExistsError,
    MethodCannotDeprecateError,
    MethodCannotVersionError,
    MethodCapabilityExecutorMismatchError,
    MethodNotFoundError,
    MethodParametersNotSubsetError,
)
from cora.recipe.aggregates.plan import (
    InvalidPlanDefaultParametersError,
    InvalidPlanNameError,
    InvalidPlanVersionTagError,
    InvalidWireError,
    PlanAffordancesNotSatisfiedError,
    PlanAlreadyExistsError,
    PlanAssetDecommissionedError,
    PlanAssetsRequiredError,
    PlanBoundMethodDeprecatedError,
    PlanBoundPracticeDeprecatedError,
    PlanCannotDeprecateError,
    PlanCannotVersionError,
    PlanFamiliesNotSatisfiedError,
    PlanNotFoundError,
    PlanPseudoAxisArityMismatchError,
    PlanPseudoAxisFanoutSignalTypeMismatchError,
    PlanPseudoAxisOutputCardinalityError,
    PlanWireAlreadyExistsError,
    PlanWireAssetNotBoundError,
    PlanWireDirectionMismatchError,
    PlanWireNotFoundError,
    PlanWirePortNotFoundError,
    PlanWireSelfLoopError,
    PlanWireSignalTypeMismatchError,
    PlanWireTargetAlreadyConnectedError,
)
from cora.recipe.aggregates.practice import (
    InvalidPracticeNameError,
    InvalidPracticeVersionTagError,
    PracticeAlreadyExistsError,
    PracticeCannotDeprecateError,
    PracticeCannotVersionError,
    PracticeNotFoundError,
)
from cora.recipe.aggregates.recipe import (
    EmptyRecipeStepsError,
    InvalidRecipeNameError,
    InvalidRecipeStepShapeError,
    InvalidRecipeVersionTagError,
    RecipeAlreadyExistsError,
    RecipeBindingReferencesUnknownParameterError,
    RecipeCannotDeprecateError,
    RecipeCannotVersionError,
    RecipeNotFoundError,
    RecipeRequiresCapabilityParametersSchemaError,
    RecipeVersionNotFoundError,
    UnboundRecipeBindingError,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features import (
    add_plan_wire,
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
    remove_plan_wire,
    update_method_parameters_schema,
    update_plan_default_parameters,
    version_capability,
    version_method,
    version_plan,
    version_practice,
    version_recipe,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    reason = exc.reason if isinstance(exc, UnauthorizedError) else str(exc)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": reason},
    )


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    """Shared 404 handler for every aggregate's NotFoundError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler for every aggregate's AlreadyExistsError.

    The decider raises these if the target stream already has events.
    In production with UUIDv7 ids this is essentially impossible, but
    the unmapped raise would surface as 500 instead of a clean 409 —
    this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    Covers the `<X>Cannot<Verb>Error` family (Method's Version /
    Deprecate; future Practice / Plan transitions). Same pattern as
    Subject / Equipment.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_unprocessable(request: Request, exc: Exception) -> JSONResponse:
    """Shared 422 handler for parse-shape failures past the Pydantic boundary.

    Covers Recipe BindingRef-against-schema mismatches, malformed step
    shapes, and unbound BindingRefs at expansion time. The 400
    Invalid<X> family is reserved for VO constructor failures
    (name / version_tag); 422 is reserved for downstream parse-shape
    or schema-cross-check failures that pass Pydantic but fail at the
    cross-aggregate boundary.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


def register_recipe_routes(app: FastAPI) -> None:
    """Attach Recipe slice routers and exception handlers to the FastAPI app."""
    app.include_router(define_method.router)
    app.include_router(get_method.router)
    app.include_router(version_method.router)
    app.include_router(deprecate_method.router)
    app.include_router(update_method_parameters_schema.router)
    app.include_router(define_practice.router)
    app.include_router(get_practice.router)
    app.include_router(version_practice.router)
    app.include_router(deprecate_practice.router)
    app.include_router(define_plan.router)
    app.include_router(get_plan.router)
    app.include_router(version_plan.router)
    app.include_router(deprecate_plan.router)
    app.include_router(update_plan_default_parameters.router)
    app.include_router(add_plan_wire.router)
    app.include_router(remove_plan_wire.router)
    app.include_router(list_methods.router)
    app.include_router(list_practices.router)
    app.include_router(list_plans.router)
    app.include_router(define_capability.router)
    app.include_router(version_capability.router)
    app.include_router(deprecate_capability.router)
    app.include_router(get_capability.router)
    app.include_router(define_recipe.router)
    app.include_router(version_recipe.router)
    app.include_router(deprecate_recipe.router)
    app.include_router(get_recipe.router)
    app.include_router(inspect_plan_binding.router)
    for validation_cls in (
        InvalidCapabilityCodeError,
        InvalidCapabilityDescriptionError,
        InvalidCapabilityNameError,
        InvalidCapabilityParametersSchemaError,
        InvalidCapabilityVersionTagError,
        InvalidExecutorShapesError,
        InvalidMethodNameError,
        InvalidMethodNeededSuppliesError,
        InvalidMethodParametersSchemaError,
        InvalidMethodVersionTagError,
        InvalidPracticeNameError,
        InvalidPracticeVersionTagError,
        InvalidPlanNameError,
        PlanAssetsRequiredError,
        InvalidPlanDefaultParametersError,
        InvalidPlanVersionTagError,
        InvalidWireError,
        # Recipe Invalid<X> name + version-tag VO constructor failures.
        InvalidRecipeNameError,
        InvalidRecipeVersionTagError,
        # Recipe __post_init__ invariant; domain error, not a Pydantic
        # boundary parse failure.
        EmptyRecipeStepsError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (
        CapabilityNotFoundError,
        MethodNotFoundError,
        PracticeNotFoundError,
        PlanNotFoundError,
        # 6h: removing a Wire that's not currently in the Plan's wire
        # set (strict-not-idempotent symmetry with PlanWireAlreadyExistsError).
        PlanWireNotFoundError,
        RecipeNotFoundError,
        RecipeVersionNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (
        CapabilityAlreadyExistsError,
        MethodAlreadyExistsError,
        PracticeAlreadyExistsError,
        PlanAlreadyExistsError,
        # 6h: re-adding an already-present Wire (strict-not-idempotent;
        # mirrors 5h add_asset_port).
        PlanWireAlreadyExistsError,
        RecipeAlreadyExistsError,
    ):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        CapabilityCannotVersionError,
        CapabilityCannotDeprecateError,
        # cross-BC guard: Method binds to Capability whose
        # executor_shapes does not include Method.
        MethodCapabilityExecutorMismatchError,
        # Method.parameters_schema is not a subset
        # of the bound Capability.parameters_schema.
        MethodParametersNotSubsetError,
        MethodCannotVersionError,
        MethodCannotDeprecateError,
        PracticeCannotVersionError,
        PracticeCannotDeprecateError,
        PlanCannotVersionError,
        PlanCannotDeprecateError,
        # Plan binding-state guards (gate-review Q5): "you cannot bind
        # to this thing because of its current state". Same 409 shape
        # as transition guards, registered together.
        PlanBoundPracticeDeprecatedError,
        PlanBoundMethodDeprecatedError,
        PlanAssetDecommissionedError,
        PlanFamiliesNotSatisfiedError,
        # cross-BC affordance-cover guard: bound Assets'
        # Family.affordances don't union to Method.capability.required_affordances.
        PlanAffordancesNotSatisfiedError,
        # 6h Plan.wires structural / cross-aggregate guards. All map
        # to 409 (state-conflict family; the wire is structurally
        # invalid given current Plan binding + Asset.ports state).
        PlanWireTargetAlreadyConnectedError,
        PlanWireAssetNotBoundError,
        PlanWirePortNotFoundError,
        PlanWireDirectionMismatchError,
        PlanWireSignalTypeMismatchError,
        PlanWireSelfLoopError,
        # PseudoAxis fan-out guards on Plan.wires (Slice 3): the
        # candidate wire would leave a PseudoAxis Asset structurally
        # inconsistent with its partition rule. All 409 (state-conflict
        # family; consistent with the structural guards above).
        PlanPseudoAxisOutputCardinalityError,
        PlanPseudoAxisArityMismatchError,
        PlanPseudoAxisFanoutSignalTypeMismatchError,
        # Recipe transition guards.
        RecipeCannotVersionError,
        RecipeCannotDeprecateError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    for unprocessable_cls in (
        # Recipe parse-shape / schema-cross-check failures past the
        # Pydantic boundary. Distinct from the Invalid<X> 400 family
        # because these fire AFTER the request body validates: the
        # wire-format step shape, the BindingRef-vs-Capability-schema
        # cross-aggregate check, the missing-schema-with-bindings case,
        # and the unbound-binding-at-expansion case.
        InvalidRecipeStepShapeError,
        RecipeBindingReferencesUnknownParameterError,
        RecipeRequiresCapabilityParametersSchemaError,
        UnboundRecipeBindingError,
    ):
        app.add_exception_handler(unprocessable_cls, _handle_unprocessable)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
