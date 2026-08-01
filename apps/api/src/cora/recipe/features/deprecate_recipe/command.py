"""The `DeprecateRecipe` command, intent dataclass for this slice.

Multi-source transition: `Defined | Versioned -> Deprecated`. Carries
the target Recipe id + an optional `replaced_by_recipe_id` pointer
for the successor (LOINC `MAP_TO` precedent matching
`Capability.replaced_by_capability_id`). When None, this is
deprecated-without-replacement.

Existing Procedures already expanded from the deprecated Recipe are
NOT automatically invalidated (advisory at BC layer per anti-hook 6
of [[project-recipe-aggregate-design]]).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecateRecipe:
    """Mark an existing Recipe as Deprecated, optionally pointing at a successor."""

    recipe_id: UUID
    reason: DeprecationReason
    replaced_by_recipe_id: UUID | None = None
