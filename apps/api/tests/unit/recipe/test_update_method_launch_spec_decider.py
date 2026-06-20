"""Unit tests for the `update_method_launch_spec` decider + the reciprocal
guard added to the `update_method_parameters_schema` decider."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from cora.recipe.aggregates.method import (
    ArgStyle,
    InvalidLaunchSpecError,
    LaunchArg,
    LaunchSpec,
    Method,
    MethodLaunchArgNotBooleanError,
    MethodLaunchArgUnknownParameterError,
    MethodLaunchSpecUpdated,
    MethodName,
    MethodNotFoundError,
    MethodParametersSchemaDropsLaunchArgError,
    MethodStatus,
)
from cora.recipe.features.update_method_launch_spec.command import UpdateMethodLaunchSpec
from cora.recipe.features.update_method_launch_spec.decider import decide
from cora.recipe.features.update_method_parameters_schema import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_method_parameters_schema import decide as schema_decide

_NOW = datetime(2026, 5, 20, tzinfo=UTC)
_MID = UUID("01900000-0000-7000-8000-0000000000a1")


def _schema(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": props,
    }


def _method(
    *, parameters_schema: dict[str, Any] | None = None, launch_spec: LaunchSpec | None = None
) -> Method:
    return Method(
        id=_MID,
        name=MethodName("recon"),
        status=MethodStatus.DEFINED,
        parameters_schema=parameters_schema,
        launch_spec=launch_spec,
    )


_RECON_SCHEMA = _schema({"num_iter": {"type": "integer"}, "remove_stripe": {"type": "boolean"}})
_RECON_SPEC = LaunchSpec(
    base_command=("tomopy", "recon"),
    args=(
        LaunchArg(name="num_iter", flag="--num-iter", required=True),
        LaunchArg(name="remove_stripe", flag="--remove-stripe", style=ArgStyle.FLAG_ONLY),
    ),
)


@pytest.mark.unit
def test_decide_raises_method_not_found_when_state_is_none() -> None:
    with pytest.raises(MethodNotFoundError):
        decide(None, UpdateMethodLaunchSpec(method_id=_MID, launch_spec=_RECON_SPEC), now=_NOW)


@pytest.mark.unit
def test_decide_emits_event_for_valid_spec_against_matching_schema() -> None:
    state = _method(parameters_schema=_RECON_SCHEMA)
    events = decide(
        state, UpdateMethodLaunchSpec(method_id=_MID, launch_spec=_RECON_SPEC), now=_NOW
    )
    assert len(events) == 1
    assert isinstance(events[0], MethodLaunchSpecUpdated)
    assert events[0].launch_spec is not None
    assert events[0].launch_spec["base_command"] == ["tomopy", "recon"]


@pytest.mark.unit
def test_decide_rejects_arg_naming_unknown_schema_key() -> None:
    state = _method(parameters_schema=_schema({"num_iter": {"type": "integer"}}))
    spec = LaunchSpec(base_command=("x",), args=(LaunchArg(name="missing", flag="--missing"),))
    with pytest.raises(MethodLaunchArgUnknownParameterError):
        decide(state, UpdateMethodLaunchSpec(method_id=_MID, launch_spec=spec), now=_NOW)


@pytest.mark.unit
def test_decide_rejects_flag_only_arg_on_non_boolean_key() -> None:
    state = _method(parameters_schema=_schema({"num_iter": {"type": "integer"}}))
    spec = LaunchSpec(
        base_command=("x",),
        args=(LaunchArg(name="num_iter", flag="--n", style=ArgStyle.FLAG_ONLY),),
    )
    with pytest.raises(MethodLaunchArgNotBooleanError):
        decide(state, UpdateMethodLaunchSpec(method_id=_MID, launch_spec=spec), now=_NOW)


@pytest.mark.unit
def test_decide_rejects_malformed_spec() -> None:
    state = _method(parameters_schema=_RECON_SCHEMA)
    bad = LaunchSpec(
        base_command=("x",), args=(LaunchArg(name="num_iter", flag="--n", position=0),)
    )
    with pytest.raises(InvalidLaunchSpecError):
        decide(state, UpdateMethodLaunchSpec(method_id=_MID, launch_spec=bad), now=_NOW)


@pytest.mark.unit
def test_decide_is_idempotent_when_spec_unchanged() -> None:
    state = _method(parameters_schema=_RECON_SCHEMA, launch_spec=_RECON_SPEC)
    assert (
        decide(state, UpdateMethodLaunchSpec(method_id=_MID, launch_spec=_RECON_SPEC), now=_NOW)
        == []
    )


@pytest.mark.unit
def test_decide_clears_spec_and_is_idempotent_on_already_clear() -> None:
    have = _method(parameters_schema=_RECON_SCHEMA, launch_spec=_RECON_SPEC)
    cleared = decide(have, UpdateMethodLaunchSpec(method_id=_MID, launch_spec=None), now=_NOW)
    assert len(cleared) == 1
    assert cleared[0].launch_spec is None

    already = _method(parameters_schema=_RECON_SCHEMA)
    assert decide(already, UpdateMethodLaunchSpec(method_id=_MID, launch_spec=None), now=_NOW) == []


# ---------- reciprocal guard in update_method_parameters_schema ----------


@pytest.mark.unit
def test_schema_update_rejected_when_it_drops_a_bound_launch_key() -> None:
    state = _method(parameters_schema=_RECON_SCHEMA, launch_spec=_RECON_SPEC)
    # drop num_iter (bound by the launch_spec)
    new_schema = _schema({"remove_stripe": {"type": "boolean"}})
    with pytest.raises(MethodParametersSchemaDropsLaunchArgError):
        schema_decide(
            state=state,
            command=UpdateMethodParametersSchema(method_id=_MID, parameters_schema=new_schema),
            capability=None,
            now=_NOW,
        )


@pytest.mark.unit
def test_schema_clear_rejected_when_launch_spec_binds_keys() -> None:
    state = _method(parameters_schema=_RECON_SCHEMA, launch_spec=_RECON_SPEC)
    with pytest.raises(MethodParametersSchemaDropsLaunchArgError):
        schema_decide(
            state=state,
            command=UpdateMethodParametersSchema(method_id=_MID, parameters_schema=None),
            capability=None,
            now=_NOW,
        )
