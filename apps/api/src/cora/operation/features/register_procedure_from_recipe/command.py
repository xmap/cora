"""The `RegisterProcedureFromRecipe` command, intent dataclass for this slice.

Carries the operator-supplied Recipe reference + bindings; the
Procedure-shape facets (name, kind, target_asset_ids, parent_run_id)
mirror `RegisterProcedure` exactly so a Procedure registered via this
slice presents the same shape as one registered via the legacy slice.
The `recipe_id` resolves cross-aggregate at handler time before the
decider runs; a missing Recipe raises `RecipeNotFoundError`. The
Recipe's `capability_id` is loaded transitively for BindingRef
re-validation + executor-shape + bindings-shape validation.

`bindings` is a free-form dict of operator-supplied parameter values
keyed by the names declared in the bound Capability's
`parameters_schema.properties`. Substituted into the Recipe's
`BindingRef` sentinels at expansion time. Empty dict is valid when
the Recipe carries no BindingRefs.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cora.shared.beam_requirement import BeamRequirement


@dataclass(frozen=True)
class RegisterProcedureFromRecipe:
    """Register a new Procedure by expanding a Recipe with operator bindings."""

    name: str
    kind: str
    target_asset_ids: tuple[UUID, ...]
    parent_run_id: UUID | None
    recipe_id: UUID
    bindings: Mapping[str, Any]
    max_consecutive_unconverged_iterations: int | None = None
    """Optional "patience" cap (>= 1 when set; None = no cap), mirroring
    RegisterProcedure. Folds onto Procedure state at register time;
    Capability-default inheritance is a deferred follow-up."""
    beam_requirement: BeamRequirement = BeamRequirement.REQUIRED
    """Whether this Procedure needs beam available to start, mirroring
    RegisterProcedure. Declared per Procedure rather than inherited from
    the Recipe's Capability: `dark_field` and `flat_field` both realize
    `cora.capability.acquisition`, yet a flat field genuinely needs beam
    (it images the beam profile) while a dark field is defined by its
    absence. The Capability is therefore the wrong grain for this axis.
    A Recipe-level default is a possible later convenience, gated on the
    same declaration existing here first."""
