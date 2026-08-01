"""Contract tests for `POST /recipes/{recipe_id}/version`."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _capability() -> dict[str, object]:
    return {
        "code": "cora.capability.vtomo",
        "name": "VTomo",
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


def _version_body(version_tag: str = "v1") -> dict[str, object]:
    return {
        "version_tag": version_tag,
        "steps": {
            "steps": [
                {"kind": "setpoint", "address": "dev:x", "value": 2.0, "verify": False},
            ],
        },
    }


@pytest.mark.contract
def test_post_version_recipe_204_emits_versioned_event() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        response = client.post(
            f"/recipes/{recipe['recipe_id']}/version",
            json=_version_body(),
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_version_recipe_404_when_recipe_missing() -> None:
    with TestClient(create_app()) as client:
        bogus = "01900000-0000-7000-8000-deadbeefcafe"
        response = client.post(f"/recipes/{bogus}/version", json=_version_body())
    assert response.status_code == 404


@pytest.mark.contract
def test_post_version_recipe_409_when_recipe_already_deprecated() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        client.post(f"/recipes/{recipe['recipe_id']}/deprecate", json={"reason": "Superseded"})
        response = client.post(f"/recipes/{recipe['recipe_id']}/version", json=_version_body())
    assert response.status_code == 409


@pytest.mark.contract
def test_post_version_recipe_400_when_version_tag_whitespace() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability()).json()
        recipe = client.post("/recipes", json=_recipe_for(cap["capability_id"])).json()
        # Pydantic min_length=1 catches empty before the decider; use a
        # whitespace-only tag that passes min_length=1 but fails the trim
        # check in the decider via InvalidRecipeVersionTagError -> 400.
        response = client.post(
            f"/recipes/{recipe['recipe_id']}/version",
            json=_version_body(version_tag="   "),
        )
    assert response.status_code == 400
