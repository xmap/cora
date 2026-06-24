"""Contract tests for `POST /procedures/{procedure_id}/conduct-until-converged`.

AUTO-align orchestration endpoint: delegates to the wired Conductor's
`conduct_until_converged`, which iterates a measure-correct pass block until a
loop-evaluated criterion over the captures bus is met OR the patience cap
trips. Covers the wire surface the default in-process wire-up delivers:

  - validation: a body missing the criterion / convergence_capture_name fails
    Pydantic parse with 422
  - validation: an unknown step kind in the pass block fails with 422
  - validation: a cap below 1 fails with 422
  - 404: an unregistered procedure raises ProcedureNotFoundError (the handler
    loads the stream up front, like conduct_procedure)
  - 200-with-failure: a recipe-LESS Procedure conducted with a literal empty
    pass block succeeds but deposits no convergence value, so the loop loud-fails
    ComputeMeasurementNotFound (the HTTP step union carries no deposit
    ComputeStep, so a hand-built empty pass cannot fill the slot)
  - 200-with-recipe-compute: a Procedure registered FROM A RECIPE carrying a
    RecipeComputeStep (with a capture_name) + a CaptureRef setpoint, conducted
    with steps:[], re-expands the pinned recipe each pass and EXECUTES the
    compute step. The default in-process ComputePort is the unseeded in-memory
    fake, so the executed step's fetch_measurements raises MeasurementNotFoundError
    (distinct from the recipe-LESS ComputeMeasurementNotFound) - proving the
    recipe compute step ran over the wire rather than the empty-pass guard firing.

Compute-driven convergence is driven over REST / MCP via the RECIPE path:
register-from-recipe with a RecipeComputeStep, then conduct-until-converged with
steps:[]. The literal HTTP / MCP step array intentionally excludes capture /
compute steps (validation-only); the recipe is the channel for them. A real
deposit + correction loop that converges end-to-end is exercised by the in-memory
scenario `tests/integration/scenarios/test_2bm_align_rotation_auto.py` (which can
seed a converging ComputePort sequence the in-process contract app cannot reach).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_PATH = "/procedures/{pid}/conduct-until-converged"
_CRITERION: dict[str, Any] = {"kind": "within_tolerance", "expected": 0.0, "tolerance": 0.5}


def _register(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "fresh proc", "kind": "rotation_alignment"}
    return UUID(client.post("/procedures", json=body).json()["procedure_id"])


@pytest.mark.contract
def test_post_conduct_until_converged_missing_criterion_returns_422() -> None:
    """The criterion is required; a body without it fails Pydantic parse."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        run = client.post(
            _PATH.format(pid=pid),
            json={"convergence_capture_name": "offset", "steps": []},
        )
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_until_converged_missing_capture_name_returns_422() -> None:
    """convergence_capture_name is required."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        run = client.post(
            _PATH.format(pid=pid),
            json={"criterion": _CRITERION, "steps": []},
        )
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_until_converged_unknown_step_kind_returns_422() -> None:
    """An unknown step kind in the pass block fails at the discriminated union."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        run = client.post(
            _PATH.format(pid=pid),
            json={
                "convergence_capture_name": "offset",
                "criterion": _CRITERION,
                "steps": [{"kind": "teleport", "address": "x", "value": 1.0}],
            },
        )
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_until_converged_cap_below_one_returns_422() -> None:
    """The patience cap must be >= 1 when supplied."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        run = client.post(
            _PATH.format(pid=pid),
            json={
                "convergence_capture_name": "offset",
                "criterion": _CRITERION,
                "steps": [],
                "max_consecutive_unconverged_iterations": 0,
            },
        )
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_until_converged_unregistered_procedure_returns_404() -> None:
    """The handler loads the Procedure stream up front -> ProcedureNotFoundError -> 404."""
    with TestClient(create_app()) as client:
        unknown_pid = uuid4()
        run = client.post(
            _PATH.format(pid=unknown_pid),
            json={"convergence_capture_name": "offset", "criterion": _CRITERION, "steps": []},
        )
    assert run.status_code == 404
    assert str(unknown_pid) in run.json()["detail"]


@pytest.mark.contract
def test_post_conduct_until_converged_empty_pass_loud_fails_absent_value() -> None:
    """An empty pass succeeds but deposits no convergence value -> loud-fail in body."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        run = client.post(
            _PATH.format(pid=pid),
            json={
                "convergence_capture_name": "offset",
                "criterion": _CRITERION,
                "steps": [],
                "max_consecutive_unconverged_iterations": 3,
            },
        )
    assert run.status_code == 200
    payload = run.json()
    assert payload["succeeded"] is False
    assert payload["failure"] is not None
    assert payload["failure"]["error_class"] == "ComputeMeasurementNotFound"


_CONVERGENCE_NAME = "rotation_center"


def _register_from_recipe_with_compute(client: TestClient) -> UUID:
    """Register a Procedure FROM a recipe carrying a RecipeComputeStep deposit.

    The recipe declares one compute step that deposits into `rotation_center`
    (the convergence-capture slot) followed by a CaptureRef setpoint reading it
    (so the recipe carries a capture/compute pair the literal HTTP step array
    cannot). The compute step runs first when the pass is conducted; the
    CaptureRef setpoint never executes (the compute step halts first against the
    unseeded in-process ComputePort).
    """
    cap = client.post(
        "/capabilities",
        json={
            "code": "cora.capability.auto_align_recipe",
            "name": "AutoAlignCap",
            "required_affordances": [],
            "executor_shapes": ["Method", "Procedure"],
        },
    ).json()
    recipe = client.post(
        "/recipes",
        json={
            "name": "auto-align recipe (compute deposit)",
            "capability_id": cap["capability_id"],
            "steps": {
                "steps": [
                    {
                        "kind": "compute",
                        "command": ["tomopy", "find_center"],
                        "input_uris": ["file:///data/2bm/align/theta_0.h5"],
                        "output_uri": None,
                        "parameters": {},
                        "capture_name": _CONVERGENCE_NAME,
                    },
                    {
                        "kind": "setpoint",
                        "address": "2bma:rot:center",
                        "value": {"__capture__": _CONVERGENCE_NAME},
                        "verify": False,
                    },
                ],
            },
        },
    ).json()
    registered = client.post(
        "/procedures/from-recipe",
        json={
            "name": "auto-align from recipe",
            "kind": "rotation_alignment",
            "target_asset_ids": [],
            "parent_run_id": None,
            "recipe_id": recipe["recipe_id"],
            "bindings": {},
        },
    )
    assert registered.status_code == 201, registered.text
    return UUID(registered.json()["procedure_id"])


@pytest.mark.contract
def test_post_conduct_until_converged_recipe_compute_step_executes_over_the_wire() -> None:
    """A recipe-backed RecipeComputeStep EXECUTES via the recipe path with steps:[].

    The handler re-expands the pinned recipe each pass, so the compute step runs
    and submits a job against the unseeded in-process ComputePort. The executed
    step's fetch_measurements raises MeasurementNotFoundError - distinct from the
    recipe-LESS empty-pass ComputeMeasurementNotFound - proving the recipe compute
    step ran over the wire, NOT a wiring / expansion error and NOT the empty-pass
    guard.
    """
    with TestClient(create_app()) as client:
        pid = _register_from_recipe_with_compute(client)
        run = client.post(
            _PATH.format(pid=pid),
            json={
                "convergence_capture_name": _CONVERGENCE_NAME,
                "criterion": _CRITERION,
                "steps": [],
                "max_consecutive_unconverged_iterations": 3,
            },
        )
    assert run.status_code == 200, run.text
    payload = run.json()
    assert payload["procedure_id"] == str(pid)
    # The compute step EXECUTED (submitted + awaited + tried to fetch a
    # measurement) and surfaced the port-level MeasurementNotFoundError, NOT the
    # loop-level ComputeMeasurementNotFound that only fires for a recipe-less
    # empty pass. This is the conduct outcome (structured failure in the body),
    # not a wiring / expansion error.
    assert payload["succeeded"] is False
    assert payload["failure"] is not None
    assert payload["failure"]["error_class"] == "MeasurementNotFoundError"
    assert payload["failure"]["source_kind"] == "compute"
    assert payload["failure"]["error_class"] != "ComputeMeasurementNotFound"
