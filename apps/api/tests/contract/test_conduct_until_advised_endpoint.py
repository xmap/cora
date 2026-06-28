"""Contract tests for `POST /procedures/{procedure_id}/conduct-until-advised`.

Steered-loop orchestration endpoint: delegates to the wired Conductor's
`conduct_until_advised`, which walks a recipe-driven pass block, hands the
accumulated evidence to an in-CORA brain (grid_walk) after each pass, and
follows its advice until it advises Stop. Covers the wire surface the default
in-process wire-up delivers:

  - validation: a body missing the objective / space / objective_capture_name
    fails Pydantic parse with 422
  - validation: an empty space (no axes) fails with 422
  - validation: an unknown objective kind fails with 422
  - 404: an unregistered procedure raises ProcedureNotFoundError (the handler
    loads the stream up front, like conduct_procedure)
  - 200-with-recipe: a Procedure registered FROM A RECIPE carrying a
    RecipeComputeStep (depositing the objective) + a SteeringRef setpoint
    (the loop-seeded axis), conducted with grid_walk, re-expands the pinned
    recipe and EXECUTES the compute step. The default in-process ComputePort is
    the unseeded in-memory fake, so the executed step's fetch_measurements
    raises MeasurementNotFoundError - proving the steered recipe (authored with
    a SteeringRef, which only a recipe can express) drove over the wire.

A real seed-the-captures loop that resolves the SteeringRef setpoint and runs to
a brain Stop is exercised in-process (a seeded ComputePort the contract app
cannot reach) by `tests/unit/operation/test_steering_ref.py`
(`test_conduct_until_advised_drives_a_steering_ref_block`).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_PATH = "/procedures/{pid}/conduct-until-advised"
_OBJECTIVE_NAME = "rotation_center"
_AXIS = "theta"
_OBJECTIVE: dict[str, Any] = {
    "kind": "Satisfy",
    "target_measurement_name": _OBJECTIVE_NAME,
    "target_value": 0.0,
}
_SPACE: dict[str, Any] = {"axes": [{"name": _AXIS, "lower": -5.0, "upper": 5.0}]}
_DECIDE: dict[str, Any] = {"substrate": "grid_walk", "points_per_axis": 3}


def _register(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "fresh proc", "kind": "rotation_center_characterization"}
    return UUID(client.post("/procedures", json=body).json()["procedure_id"])


def _body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "objective": _OBJECTIVE,
        "space": _SPACE,
        "objective_capture_name": _OBJECTIVE_NAME,
        "decide": _DECIDE,
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_conduct_until_advised_missing_objective_returns_422() -> None:
    """The objective is required; a body without it fails Pydantic parse."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        body = _body()
        del body["objective"]
        run = client.post(_PATH.format(pid=pid), json=body)
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_until_advised_missing_space_returns_422() -> None:
    """The space is required."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        body = _body()
        del body["space"]
        run = client.post(_PATH.format(pid=pid), json=body)
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_until_advised_empty_space_returns_422() -> None:
    """A space with no axes fails (min_length=1)."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        run = client.post(_PATH.format(pid=pid), json=_body(space={"axes": []}))
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_until_advised_unknown_objective_kind_returns_422() -> None:
    """An objective kind outside the enum fails at parse."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        run = client.post(
            _PATH.format(pid=pid),
            json=_body(objective={"kind": "Teleport", "target_measurement_name": _OBJECTIVE_NAME}),
        )
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_until_advised_unregistered_procedure_returns_404() -> None:
    """The handler loads the Procedure stream up front -> ProcedureNotFoundError -> 404."""
    with TestClient(create_app()) as client:
        unknown_pid = uuid4()
        run = client.post(_PATH.format(pid=unknown_pid), json=_body())
    assert run.status_code == 404
    assert str(unknown_pid) in run.json()["detail"]


@pytest.mark.contract
def test_post_conduct_until_advised_space_axis_not_consumed_returns_422() -> None:
    """A space axis not consumed by a recipe SteeringRef setpoint is unprocessable.

    A recipe-less Procedure conducts with steps from its (empty) pinned recipe, so
    no SteeringRef setpoint consumes `theta`. The Conductor's pre-FSM wire guard
    rejects the request; the handler maps that ValueError to a 422
    (SteeringWireMismatchError), NOT a 500, surfacing a client-correctable
    mismatch between the request's space and the recipe.
    """
    with TestClient(create_app()) as client:
        pid = _register(client)  # recipe-less: no steering setpoints
        run = client.post(_PATH.format(pid=pid), json=_body())
    assert run.status_code == 422


def _register_from_steered_recipe(client: TestClient) -> UUID:
    """Register a Procedure FROM a recipe carrying a compute deposit + a SteeringRef setpoint.

    The recipe declares a compute step that deposits into `rotation_center` (the
    objective slot the brain reads) followed by a SteeringRef setpoint reading
    the loop-seeded `theta` axis. The SteeringRef value can ONLY be expressed in
    a recipe (the literal HTTP step array has no SteeringRef arm), so this proves
    the W1 value-kind flows through the recipe-define wire. The compute step runs
    first when conducted; it halts against the unseeded in-process ComputePort,
    so the SteeringRef setpoint never executes (parity with the converged test).
    """
    cap = client.post(
        "/capabilities",
        json={
            "code": "cora.capability.steered_align_recipe",
            "name": "SteeredAlignCap",
            "required_affordances": [],
            "executor_shapes": ["Method", "Procedure"],
        },
    ).json()
    recipe = client.post(
        "/recipes",
        json={
            "name": "steered align recipe (compute deposit + steering setpoint)",
            "capability_id": cap["capability_id"],
            "steps": {
                "steps": [
                    {
                        "kind": "compute",
                        "command": ["tomopy", "find_center"],
                        "input_uris": ["file:///data/19bm/align/theta_pair.h5"],
                        "output_uri": None,
                        "parameters": {},
                        "capture_name": _OBJECTIVE_NAME,
                    },
                    {
                        "kind": "setpoint",
                        "address": "19bm:sample_rotary_theta",
                        "value": {"__steering__": _AXIS},
                        "verify": False,
                    },
                ],
            },
        },
    ).json()
    registered = client.post(
        "/procedures/from-recipe",
        json={
            "name": "steered align from recipe",
            "kind": "rotation_center_characterization",
            "target_asset_ids": [],
            "parent_run_id": None,
            "recipe_id": recipe["recipe_id"],
            "bindings": {},
        },
    )
    assert registered.status_code == 201, registered.text
    return UUID(registered.json()["procedure_id"])


@pytest.mark.contract
def test_post_conduct_until_advised_steered_recipe_executes_over_the_wire() -> None:
    """A SteeringRef-authored recipe drives conduct_until_advised over the wire.

    The recipe (with a SteeringRef setpoint that only a recipe can express) is
    defined + registered over HTTP, then conducted with grid_walk and steps from
    the pinned recipe. The compute step EXECUTES against the unseeded in-process
    ComputePort and surfaces MeasurementNotFoundError - a structured failure in
    the body (not a wiring / validation error), proving the steered recipe ran
    end-to-end over the wire.
    """
    with TestClient(create_app()) as client:
        pid = _register_from_steered_recipe(client)
        run = client.post(_PATH.format(pid=pid), json=_body())
    assert run.status_code == 200, run.text
    payload = run.json()
    assert payload["procedure_id"] == str(pid)
    assert payload["succeeded"] is False
    assert payload["failure"] is not None
    assert payload["failure"]["error_class"] == "MeasurementNotFoundError"
    assert payload["failure"]["source_kind"] == "compute"
