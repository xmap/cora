"""The `UpdateMethodLaunchSpec` command: intent dataclass for this slice.

Operators set, replace, or clear a Method's vetted compute launch
recipe (`launch_spec`), so a conduct caller selects this recipe instead
of POSTing raw argv. Independent of the Defined / Versioned / Deprecated
lifecycle, mirroring `update_method_parameters_schema`.

`launch_spec=None` is a valid intent (clear the recipe). The decider
validates well-formedness (`validate_launch_spec`) and cross-checks each
`LaunchArg.name` against the Method's current `parameters_schema` before
emitting `MethodLaunchSpecUpdated`. See
[[project-method-launch-spec-stage0-design]].
"""

from dataclasses import dataclass
from uuid import UUID

from cora.recipe.aggregates.method import LaunchSpec


@dataclass(frozen=True)
class UpdateMethodLaunchSpec:
    """Set / replace / clear a Method's launch_spec."""

    method_id: UUID
    launch_spec: LaunchSpec | None
