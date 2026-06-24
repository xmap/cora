"""Recipe aggregate: state, status, errors, events, evolver, read.

The deployment-bound executable step sequence at the operations layer
per [[project-recipe-aggregate-design]]; sits beside Capability rather
than absorbing Method/Plan per the [[capability-naming-split-lock]]
Shape 2 decision. References `capability_id` (REQUIRED + IMMUTABLE
across versions); carries the templated `steps` tuple that expands to
a flat `Step` list at `register_procedure_from_recipe` time.

Vertical slices that operate on this aggregate live under
`cora.recipe.features.<verb>_recipe/` and import from here for state,
events, and error types.
"""

from cora.recipe.aggregates.recipe.body import (
    BindingRef,
    CaptureRef,
    DuplicateRecipeCaptureError,
    InvalidRecipeStepShapeError,
    RecipeActionStep,
    RecipeCaptureStep,
    RecipeCheckStep,
    RecipeComputeStep,
    RecipeSetpointStep,
    RecipeStep,
    UnboundRecipeBindingError,
    UnboundRecipeCaptureError,
    resolve_value,
    validate_capture_refs,
)
from cora.recipe.aggregates.recipe.body import (
    from_dict as steps_from_dict,
)
from cora.recipe.aggregates.recipe.body import (
    to_dict as steps_to_dict,
)
from cora.recipe.aggregates.recipe.events import (
    RecipeDefined,
    RecipeDeprecated,
    RecipeEvent,
    RecipeVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.recipe.aggregates.recipe.evolver import evolve, fold
from cora.recipe.aggregates.recipe.read import (
    RecipeLifecycleTimestamps,
    load_recipe,
    load_recipe_at_version,
    load_recipe_timestamps,
)
from cora.recipe.aggregates.recipe.state import (
    RECIPE_NAME_MAX_LENGTH,
    RECIPE_VERSION_TAG_MAX_LENGTH,
    EmptyRecipeStepsError,
    InvalidRecipeNameError,
    InvalidRecipeVersionTagError,
    Recipe,
    RecipeAlreadyExistsError,
    RecipeCannotDeprecateError,
    RecipeCannotVersionError,
    RecipeName,
    RecipeNotFoundError,
    RecipeStatus,
    RecipeVersionNotFoundError,
)
from cora.recipe.aggregates.recipe.steps_validation import (
    RecipeBindingReferencesUnknownParameterError,
    RecipeRequiresCapabilityParametersSchemaError,
    collect_binding_names,
    validate_recipe_steps_against_capability_schema,
)

__all__ = [
    "RECIPE_NAME_MAX_LENGTH",
    "RECIPE_VERSION_TAG_MAX_LENGTH",
    "BindingRef",
    "CaptureRef",
    "DuplicateRecipeCaptureError",
    "EmptyRecipeStepsError",
    "InvalidRecipeNameError",
    "InvalidRecipeStepShapeError",
    "InvalidRecipeVersionTagError",
    "Recipe",
    "RecipeActionStep",
    "RecipeAlreadyExistsError",
    "RecipeBindingReferencesUnknownParameterError",
    "RecipeCannotDeprecateError",
    "RecipeCannotVersionError",
    "RecipeCaptureStep",
    "RecipeCheckStep",
    "RecipeComputeStep",
    "RecipeDefined",
    "RecipeDeprecated",
    "RecipeEvent",
    "RecipeLifecycleTimestamps",
    "RecipeName",
    "RecipeNotFoundError",
    "RecipeRequiresCapabilityParametersSchemaError",
    "RecipeSetpointStep",
    "RecipeStatus",
    "RecipeStep",
    "RecipeVersionNotFoundError",
    "RecipeVersioned",
    "UnboundRecipeBindingError",
    "UnboundRecipeCaptureError",
    "collect_binding_names",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_recipe",
    "load_recipe_at_version",
    "load_recipe_timestamps",
    "resolve_value",
    "steps_from_dict",
    "steps_to_dict",
    "to_payload",
    "validate_capture_refs",
    "validate_recipe_steps_against_capability_schema",
]
