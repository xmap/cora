"""Contract tests for `POST /recipes/{recipe_id}/deprecate`."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _capability() -> dict[str, object]:
    return {
        "code": "cora.capability.dtomo",
        "name": "DTomo",
        "required_affordances": [],
        "executor_shapes": ["Method", "Procedure"],
    }


def _recipe_for(capability_id: str) -> dict[str, object]:
    return {
        "name": "R",
        "capability_id": capability_id,
        "steps": {
            "steps": [
                {"kind": "setpoint", "address": "dev:x", "value": 1.0, "verify": False},
            ],
        },
    }


@pytest.mark.contract
def test_post_deprecate_recipe_204_emits_deprecated_event() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        response = client.post(
            f"/recipes/{recipe['recipe_id']}/deprecate", json={"reason": "Superseded"}
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_recipe_accepts_replaced_by_recipe_id() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        successor = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        response = client.post(
            f"/recipes/{recipe['recipe_id']}/deprecate",
            json={"reason": "Superseded", "replaced_by_recipe_id": successor["recipe_id"]},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_recipe_404_when_recipe_missing() -> None:
    with TestClient(create_app()) as client:
        bogus = "01900000-0000-7000-8000-deadbeefcafe"
        response = client.post(f"/recipes/{bogus}/deprecate", json={"reason": "Superseded"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_deprecate_recipe_409_on_re_deprecate() -> None:
    """Strict-not-idempotent: re-deprecating raises 409."""
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        client.post(f"/recipes/{recipe['recipe_id']}/deprecate", json={"reason": "Superseded"})
        response = client.post(
            f"/recipes/{recipe['recipe_id']}/deprecate", json={"reason": "Superseded"}
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_deprecate_missing_reason_returns_422() -> None:
    """`reason` is required: an empty body is a schema rejection."""
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        response = client.post(f"/recipes/{recipe['recipe_id']}/deprecate", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_deprecate_unknown_reason_returns_422() -> None:
    """`reason` is a closed enum: prose is rejected at the schema."""
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        response = client.post(
            f"/recipes/{recipe['recipe_id']}/deprecate",
            json={"reason": "superseded by a newer one"},
        )
    assert response.status_code == 422
