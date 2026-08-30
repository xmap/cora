"""Contract tests for `GET /recipes/{recipe_id}`."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _capability() -> dict[str, object]:
    return {
        "code": "cora.capability.gtomo",
        "name": "GTomo",
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
def test_get_recipe_200_returns_full_recipe_response() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        response = client.get(f"/recipes/{recipe['recipe_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == recipe["recipe_id"]
    assert body["capability_id"] == cap["capability_id"]
    assert body["status"] == "Defined"
    assert body["version"] is None
    assert body["replaced_by_recipe_id"] is None
    assert "steps" in body
    assert body["steps"]["steps"][0]["kind"] == "setpoint"


@pytest.mark.contract
def test_get_recipe_surfaces_closing_steps() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        body = _recipe_for(cap["capability_id"])
        body["closing_steps"] = {
            "steps": [
                {"kind": "setpoint", "address": "dev:shutter", "value": 0.0, "verify": False},
            ],
        }
        recipe = client.post("/recipes", json=body).json()
        response = client.get(f"/recipes/{recipe['recipe_id']}")
    assert response.status_code == 200
    resp_body = response.json()
    assert resp_body["closing_steps"]["steps"][0]["address"] == "dev:shutter"


@pytest.mark.contract
def test_get_recipe_defaults_closing_steps_to_empty() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        response = client.get(f"/recipes/{recipe['recipe_id']}")
    assert response.json()["closing_steps"]["steps"] == []


@pytest.mark.contract
def test_get_recipe_404_when_recipe_missing() -> None:
    with TestClient(create_app()) as client:
        bogus = "01900000-0000-7000-8000-deadbeefcafe"
        response = client.get(f"/recipes/{bogus}")
    assert response.status_code == 404


@pytest.mark.contract
def test_get_recipe_reflects_versioned_state_after_version_recipe_call() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        client.post(
            f"/recipes/{recipe['recipe_id']}/version",
            json={
                "version_tag": "v2",
                "steps": {
                    "steps": [
                        {
                            "kind": "setpoint",
                            "address": "dev:x",
                            "value": 9.0,
                            "verify": False,
                        }
                    ]
                },
            },
        )
        response = client.get(f"/recipes/{recipe['recipe_id']}")
    body = response.json()
    assert body["status"] == "Versioned"
    assert body["version"] == "v2"
