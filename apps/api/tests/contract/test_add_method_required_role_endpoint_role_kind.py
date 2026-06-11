"""Contract tests for the role_kind path of POST /methods/{id}/add-required-role.

Layer 3 sub-slice 3D. Mirror of the slice-1 family_id-path contract
tests for the new XOR target. Covers 201 happy path, 404 on
unresolved role_kind, 422 on XOR violations (both-set / neither-set).
"""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def _define_method(client: TestClient, name: str = "Tomography") -> UUID:
    cap_id = create_capability_via_api(client)
    response = client.post(
        "/methods",
        json={"name": name, "capability_id": cap_id, "needed_family_ids": []},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["method_id"])


def _create_imager_role(client: TestClient, app: FastAPI) -> UUID:
    response = client.post(
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
    assert response.status_code == 201, response.text
    role_id = UUID(response.json()["role_id"])
    # Test-env: no projection worker runs, so seed RoleLookup
    # directly via the in-memory adapter (same pattern as 3B/3C
    # contract tests).
    app.state.deps.role_lookup.register(
        role_id=role_id,
        name="Imager",
        required_affordances=["Imageable"],
    )
    return role_id


def _requirement_body_role_kind(role_id: UUID) -> dict[str, object]:
    return {
        "role_name": "detector",
        "role_kind": str(role_id),
        "required_ports": [],
        "optional": False,
    }


@pytest.mark.contract
def test_post_returns_201_for_role_kind_when_role_resolves() -> None:
    app = create_app()
    with TestClient(app) as client:
        method_id = _define_method(client)
        role_id = _create_imager_role(client, app)
        response = client.post(
            f"/methods/{method_id}/add-required-role",
            json={"requirement": _requirement_body_role_kind(role_id)},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_returns_404_when_role_kind_does_not_resolve() -> None:
    """Handler-side RoleLookup precondition raises RoleNotFoundError -> 404."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        # Use a fresh UUID never registered with RoleLookup.
        response = client.post(
            f"/methods/{method_id}/add-required-role",
            json={
                "requirement": _requirement_body_role_kind(
                    UUID("00000000-0000-0000-0000-000000000999")
                )
            },
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_returns_422_when_both_role_kind_and_family_id_set() -> None:
    """Pydantic wire-layer XOR check fires before the domain VO."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/add-required-role",
            json={
                "requirement": {
                    "role_name": "detector",
                    "role_kind": "00000000-0000-0000-0000-000000000001",
                    "family_id": "00000000-0000-0000-0000-000000000002",
                    "required_ports": [],
                    "optional": False,
                }
            },
        )
    assert response.status_code == 422, response.text


@pytest.mark.contract
def test_post_returns_422_when_neither_role_kind_nor_family_id_set() -> None:
    """Neither-set also catches at the wire layer (422)."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/add-required-role",
            json={
                "requirement": {
                    "role_name": "detector",
                    "required_ports": [],
                    "optional": False,
                }
            },
        )
    assert response.status_code == 422, response.text
