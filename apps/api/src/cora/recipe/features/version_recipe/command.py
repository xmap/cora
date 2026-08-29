"""The `VersionRecipe` command, intent dataclass for this slice.

Multi-source transition: `Defined | Versioned -> Versioned`. The
supplied `steps` REPLACE the prior wholesale (a new version IS a new
declaration; Pattern P; matches Method/Plan/Practice/Family /
Capability replace-on-version precedent).

`capability_id` is NOT part of this command; it's PRESERVED from the
prior Recipe state (immutable across versions per anti-hook 3 of
[[project-recipe-aggregate-design]]). Re-binding to a different
Capability requires authoring a new Recipe.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.recipe.aggregates.recipe import RecipeStep


@dataclass(frozen=True)
class VersionRecipe:
    """Issue a new version label + replacement steps for an existing Recipe.

    `closing_steps` is additive and optional (default `()`); it
    REPLACES wholesale alongside `steps`. See `Recipe.closing_steps`.
    """

    recipe_id: UUID
    version_tag: str
    steps: tuple[RecipeStep, ...]
    closing_steps: tuple[RecipeStep, ...] = ()
