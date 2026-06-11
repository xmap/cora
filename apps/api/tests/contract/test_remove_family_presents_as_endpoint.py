"""Contract tests for `POST /families/{family_id}/remove-presents-as`.

Action endpoint with body `{role_id}`. 204 on success; 404 if Family
not found; 409 on strict-not-idempotent (Role not advertised).
"""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _seed_family_with_imager(client: TestClient, app: FastAPI) -> tuple[str, str]:
    """Create Camera Family + Imager Role + advertise. Return (family_id, role_id)."""
    family_resp = client.post(
        "/families",
        json={"name": "Camera", "affordances": ["Imageable"]},
    )
    family_id = str(family_resp.json()["family_id"])
    role_resp = client.post(
        "/roles",
        json={
            "name": "Diagnostician",
            "docstring": "Acquires 2D image frames.",
            "required_affordances": ["Imageable"],
            "optional_affordances": [],
            "produces": [],
            "consumes": [],
        },
    )
    role_id = str(role_resp.json()["role_id"])
    # Seed in-memory RoleLookup so add-presents-as handler resolves it.
    app.state.deps.role_lookup.register(
        role_id=UUID(role_id),
        name="Imager",
        required_affordances=["Imageable"],
    )
    add_resp = client.post(
        f"/families/{family_id}/add-presents-as",
        json={"role_id": role_id},
    )
    assert add_resp.status_code == 204, add_resp.text
    return family_id, role_id


@pytest.mark.contract
def test_post_remove_presents_as_returns_204_on_success() -> None:
    app = create_app()
    with TestClient(app) as client:
        family_id, role_id = _seed_family_with_imager(client, app)
        response = client.post(
            f"/families/{family_id}/remove-presents-as",
            json={"role_id": role_id},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_remove_presents_as_returns_404_for_missing_family() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/families/00000000-0000-0000-0000-000000000999/remove-presents-as",
            json={"role_id": "00000000-0000-0000-0000-000000000888"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_remove_presents_as_returns_409_when_role_not_advertised() -> None:
    """Strict-not-idempotent: removing a Role the Family does not advertise."""
    with TestClient(create_app()) as client:
        family_resp = client.post(
            "/families",
            json={"name": "Camera", "affordances": ["Imageable"]},
        )
        family_id = str(family_resp.json()["family_id"])
        role_resp = client.post(
            "/roles",
            json={
                "name": "Diagnostician",
                "docstring": "Acquires 2D image frames.",
                "required_affordances": ["Imageable"],
                "optional_affordances": [],
                "produces": [],
                "consumes": [],
            },
        )
        role_id = str(role_resp.json()["role_id"])
        response = client.post(
            f"/families/{family_id}/remove-presents-as",
            json={"role_id": role_id},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_remove_presents_as_double_remove_returns_409() -> None:
    """First remove succeeds; second raises strict-not-idempotent."""
    app = create_app()
    with TestClient(app) as client:
        family_id, role_id = _seed_family_with_imager(client, app)
        first = client.post(
            f"/families/{family_id}/remove-presents-as",
            json={"role_id": role_id},
        )
        second = client.post(
            f"/families/{family_id}/remove-presents-as",
            json={"role_id": role_id},
        )
    assert first.status_code == 204
    assert second.status_code == 409
