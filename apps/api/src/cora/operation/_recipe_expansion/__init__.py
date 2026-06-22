"""Recipe step-resolution subpackage for the Operation BC.

Carved from the BC root once the private-module count crossed the ~10-file
threshold (see docs/reference/layout.md; the equipment `_bodies/` / `_pidinst/`
carve is the precedent). Groups the three private modules that turn a Recipe's
parameterized step tuple into the concrete `Step` list a Procedure conducts, and
that replay / verify that resolution:

  - `_expand`: the pure `expand(steps, bindings) -> Step list` substitution kernel
    (+ `steps_to_wire` / `canonical_json_bytes` for provenance hashing).
  - `_replay`: locate + verify the genesis `RecipeExpansionRecorded` provenance
    on the `conduct_procedure` path (re-expand and compare pinned hashes).
  - `_resolved_steps_replay`: locate the pinned `ResolvedStepsRecorded` provenance
    on the `reconduct_procedure` (resume) path.

Re-exports the public surface so consumers import from the package
(`from cora.operation._recipe_expansion import expand, find_recipe_expansion_record`).
"""

from cora.operation._recipe_expansion._expand import (
    canonical_json_bytes,
    expand,
    steps_to_wire,
)
from cora.operation._recipe_expansion._replay import (
    MismatchField,
    RecipeExpansionPins,
    find_recipe_expansion_record,
    pins_from_payload,
    verify_bindings_hash,
    verify_steps_hash,
)
from cora.operation._recipe_expansion._resolved_steps_replay import (
    find_resolved_steps_record,
)

__all__ = [
    "MismatchField",
    "RecipeExpansionPins",
    "canonical_json_bytes",
    "expand",
    "find_recipe_expansion_record",
    "find_resolved_steps_record",
    "pins_from_payload",
    "steps_to_wire",
    "verify_bindings_hash",
    "verify_steps_hash",
]
