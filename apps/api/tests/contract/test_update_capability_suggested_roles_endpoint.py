"""Contract tests for POST /capabilities/{capability_id}/suggested-roles (3E)."""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_capability(client: TestClient) -> UUID:
    response = client.post(
        "/capabilities",
        json={
            "code": "cora.capability.acquire",
            "name": "Acquire",
            "required_affordances": [],
            "executor_shapes": ["Method"],
        },
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["capability_id"])


def _create_role(
    client: TestClient,
    app: FastAPI,
    *,
    name: str = "Diagnostician",
) -> UUID:
    response = client.post(
        "/roles",
        json={
            "name": name,
            "docstring": "Acquires 2D image frames.",
            "required_affordances": ["Imageable"],
            "optional_affordances": [],
            "produces": [],
            "consumes": [],
        },
    )
    assert response.status_code == 201, response.text
    role_id = UUID(response.json()["role_id"])
    # In app_env=test the projection worker does not run, so seed
    # the in-memory RoleLookup directly (same pattern as 3B/3C/3D).
    app.state.deps.role_lookup.register(
        role_id=role_id,
        name=name,
        required_affordances=["Imageable"],
    )
    return role_id


@pytest.mark.contract
def test_post_returns_204_on_successful_update() -> None:
    app = create_app()
    with TestClient(app) as client:
        capability_id = _define_capability(client)
        role_a = _create_role(client, app, name="Diagnostician")
        role_b = _create_role(client, app, name="Cartographer")
        response = client.post(
            f"/capabilities/{capability_id}/suggested-roles",
            json={"suggested_role_ids": [str(role_a), str(role_b)]},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_accepts_empty_set_to_clear_suggested_roles() -> None:
    """Wholesale-replace shape: empty list clears the column."""
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(
            f"/capabilities/{capability_id}/suggested-roles",
            json={"suggested_role_ids": []},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_returns_404_when_role_id_unresolved() -> None:
    """Handler-side RoleLookup precondition raises RoleNotFoundError."""
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(
            f"/capabilities/{capability_id}/suggested-roles",
            json={"suggested_role_ids": ["00000000-0000-0000-0000-000000000999"]},
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_returns_404_when_capability_unknown() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/capabilities/00000000-0000-0000-0000-000000000999/suggested-roles",
            json={"suggested_role_ids": []},
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_rejects_malformed_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(
            f"/capabilities/{capability_id}/suggested-roles",
            json={"suggested_role_ids": ["not-a-uuid"]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_idempotent_wholesale_republish_returns_204() -> None:
    """Wholesale-replace is NOT strict-not-idempotent at the wire layer."""
    app = create_app()
    with TestClient(app) as client:
        capability_id = _define_capability(client)
        role_id = _create_role(client, app)
        body = {"suggested_role_ids": [str(role_id)]}
        first = client.post(f"/capabilities/{capability_id}/suggested-roles", json=body)
        second = client.post(f"/capabilities/{capability_id}/suggested-roles", json=body)
    assert first.status_code == 204
    assert second.status_code == 204
