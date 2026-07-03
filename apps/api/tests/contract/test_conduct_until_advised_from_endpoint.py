"""Contract tests for `POST /procedures/{procedure_id}/conduct-until-advised-from`.

Steered-RESUME orchestration endpoint: resumes a Held GP-steered Procedure by
re-seeding the brain from the recorded closed passes and continuing the loop at
the open frontier. Covers the wire surface the default in-process wire-up
delivers:

  - validation: a body missing the objective / space / objective_capture_name
    fails Pydantic parse with 422
  - 404: an unregistered Procedure raises ProcedureNotFoundError (the handler
    loads the stream up front)
  - 409: a Defined (never-conducted, non-Held) Procedure cannot be resumed
    (ProcedureCannotResumeError)

The full seed-the-captures resume that runs to a brain Stop needs a seeded
in-process ComputePort the contract app cannot reach; it is exercised by
`tests/unit/operation/test_conduct_until_advised_from_handler.py`.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_PATH = "/procedures/{pid}/conduct-until-advised-from"
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
def test_post_conduct_until_advised_from_missing_objective_returns_422() -> None:
    """The objective is required; a body without it fails Pydantic parse."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        body = _body()
        del body["objective"]
        run = client.post(_PATH.format(pid=pid), json=body)
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_until_advised_from_missing_space_returns_422() -> None:
    """The space is required."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        body = _body()
        del body["space"]
        run = client.post(_PATH.format(pid=pid), json=body)
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_until_advised_from_unregistered_procedure_returns_404() -> None:
    """The handler loads the Procedure stream up front -> ProcedureNotFoundError -> 404."""
    with TestClient(create_app()) as client:
        unknown_pid = uuid4()
        run = client.post(_PATH.format(pid=unknown_pid), json=_body())
    assert run.status_code == 404
    assert str(unknown_pid) in run.json()["detail"]


@pytest.mark.contract
def test_post_conduct_until_advised_from_non_held_procedure_returns_409() -> None:
    """A Defined (never-conducted) Procedure is not Held -> 409, no resume."""
    with TestClient(create_app()) as client:
        pid = _register(client)  # status Defined, not Held
        run = client.post(_PATH.format(pid=pid), json=_body())
    assert run.status_code == 409
    assert str(pid) in run.json()["detail"]
