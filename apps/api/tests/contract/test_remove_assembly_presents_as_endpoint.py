"""Contract tests for `POST /assemblies/{assembly_id}/remove-presents-as`."""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _seed_assembly_with_role(client: TestClient, app: FastAPI) -> tuple[UUID, UUID]:
    family_resp = client.post(
        "/families",
        json={"name": "Imager", "affordances": []},
    )
    family_id = UUID(family_resp.json()["family_id"])
    asm_resp = client.post(
        "/assemblies",
        json={
            "name": "MCTOptics",
            "presents_as_family_id": str(family_id),
            "required_slots": [],
            "required_wires": [],
        },
    )
    assembly_id = UUID(asm_resp.json()["assembly_id"])
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
    role_id = UUID(role_resp.json()["role_id"])
    app.state.deps.role_lookup.register(
        role_id=role_id,
        name="Imager",
        required_affordances=["Imageable"],
    )
    add_resp = client.post(
        f"/assemblies/{assembly_id}/add-presents-as",
        json={"role_id": str(role_id)},
    )
    assert add_resp.status_code == 204, add_resp.text
    return assembly_id, role_id


@pytest.mark.contract
def test_post_remove_presents_as_returns_204_on_success() -> None:
    app = create_app()
    with TestClient(app) as client:
        assembly_id, role_id = _seed_assembly_with_role(client, app)
        response = client.post(
            f"/assemblies/{assembly_id}/remove-presents-as",
            json={"role_id": str(role_id)},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_remove_presents_as_returns_404_for_missing_assembly() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assemblies/00000000-0000-0000-0000-000000000999/remove-presents-as",
            json={"role_id": "00000000-0000-0000-0000-000000000888"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_remove_presents_as_returns_409_when_role_not_advertised() -> None:
    with TestClient(create_app()) as client:
        family_resp = client.post(
            "/families",
            json={"name": "Imager", "affordances": []},
        )
        family_id = UUID(family_resp.json()["family_id"])
        asm_resp = client.post(
            "/assemblies",
            json={
                "name": "MCTOptics",
                "presents_as_family_id": str(family_id),
                "required_slots": [],
                "required_wires": [],
            },
        )
        assembly_id = UUID(asm_resp.json()["assembly_id"])
        response = client.post(
            f"/assemblies/{assembly_id}/remove-presents-as",
            json={"role_id": "00000000-0000-0000-0000-000000000888"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_remove_presents_as_double_remove_returns_409() -> None:
    app = create_app()
    with TestClient(app) as client:
        assembly_id, role_id = _seed_assembly_with_role(client, app)
        first = client.post(
            f"/assemblies/{assembly_id}/remove-presents-as",
            json={"role_id": str(role_id)},
        )
        second = client.post(
            f"/assemblies/{assembly_id}/remove-presents-as",
            json={"role_id": str(role_id)},
        )
    assert first.status_code == 204
    assert second.status_code == 409
