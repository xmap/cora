"""Pure decider for the `UpdateMethodLaunchSpec` command.

Validates the launch_spec's well-formedness, then cross-checks it
against the Method's CURRENT parameters_schema (already on state, so no
cross-BC load): every `LaunchArg.name` must be a schema property, and a
`flag_only` arg's property must be `type: boolean`.

Launch-spec updates are orthogonal to lifecycle (Defined / Versioned /
Deprecated all permit them), so no source-state check. content_hash is
preserved across the update (the drift from the last versioned hash is
the intended "uncommitted changes" signal, like the schema slice).

## Idempotency: no-op on unchanged

If the proposed launch_spec equals the current one (including both
None), no event is emitted (mirrors update_method_parameters_schema).

Invariants:
  - State must not be None -> MethodNotFoundError
  - launch_spec (if non-None) must be well-formed -> InvalidLaunchSpecError
  - each LaunchArg.name must be a parameters_schema property ->
    MethodLaunchArgUnknownParameterError
  - a flag_only LaunchArg's schema property must be boolean ->
    MethodLaunchArgNotBooleanError
  - If proposed == current, return [] (no event emitted)
"""

from datetime import datetime
from typing import Any, cast

from cora.recipe.aggregates.method import (
    ArgStyle,
    Method,
    MethodLaunchArgNotBooleanError,
    MethodLaunchArgUnknownParameterError,
    MethodLaunchSpecUpdated,
    MethodNotFoundError,
    launch_spec_to_dict,
    validate_launch_spec,
)
from cora.recipe.features.update_method_launch_spec.command import UpdateMethodLaunchSpec


def decide(
    state: Method | None,
    command: UpdateMethodLaunchSpec,
    *,
    now: datetime,
) -> list[MethodLaunchSpecUpdated]:
    """Decide the events produced by updating a Method's launch_spec."""
    if state is None:
        raise MethodNotFoundError(command.method_id)

    spec = command.launch_spec
    if spec is not None:
        validate_launch_spec(spec)
        properties: dict[str, Any] = {}
        if state.parameters_schema is not None:
            properties = state.parameters_schema.get("properties", {})
        for arg in spec.args:
            if arg.name not in properties:
                raise MethodLaunchArgUnknownParameterError(state.id, arg.name)
            if arg.style is ArgStyle.FLAG_ONLY:
                # A validated parameters_schema property is a JSON object;
                # cast keeps the boolean-type check pyright-clean.
                prop = cast("dict[str, Any]", properties[arg.name])
                if prop.get("type") != "boolean":
                    raise MethodLaunchArgNotBooleanError(state.id, arg.name)

    if spec == state.launch_spec:
        return []
    return [
        MethodLaunchSpecUpdated(
            method_id=state.id,
            launch_spec=launch_spec_to_dict(spec) if spec is not None else None,
            occurred_at=now,
        )
    ]
