"""Contract tests for `GET /fixtures/{fixture_id}`.

Covers happy-path 200, 404 on unknown Fixture, full-state response
shape (slot_asset_bindings + parameter_overrides included).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_family(client: TestClient) -> UUID:
    response = client.post("/families", json={"name": "Detector", "affordances": []})
    assert response.status_code == 201, response.text
    return UUID(response.json()["family_id"])


def _register_asset(client: TestClient, family_id: UUID) -> UUID:
    create = client.post(
        "/assets",
        json={"name": "Camera-1", "tier": "Device", "parent_id": str(uuid4())},
    )
    assert create.status_code == 201, create.text
    asset_id = UUID(create.json()["asset_id"])
    add = client.post(
        f"/assets/{asset_id}/add-family",
        json={"family_id": str(family_id)},
    )
    assert add.status_code == 204, add.text
    return asset_id


def _define_assembly(client: TestClient, family_id: UUID) -> UUID:
    response = client.post(
        "/assemblies",
        json={
            "name": "MCTOptics",
            "presents_as_family_id": str(family_id),
            "required_slots": [
                {
                    "slot_name": "camera",
                    "required_family_ids": [str(family_id)],
                    "cardinality": "Exactly1",
                }
            ],
            "required_wires": [],
        },
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["assembly_id"])


def _register_fixture(client: TestClient, assembly_id: UUID, asset_id: UUID) -> UUID:
    response = client.post(
        f"/assemblies/{assembly_id}/fixtures",
        json={
            "slot_asset_bindings": [{"slot_name": "camera", "asset_id": str(asset_id)}],
            "parameter_overrides": {},
        },
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["fixture_id"])


@pytest.mark.contract
def test_get_fixture_returns_200_with_full_state_on_hit() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        assembly_id = _define_assembly(client, family_id)
        fixture_id = _register_fixture(client, assembly_id, asset_id)
        response = client.get(f"/fixtures/{fixture_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(fixture_id)
    assert body["assembly_id"] == str(assembly_id)
    assert body["assembly_content_hash"]
    assert body["slot_asset_bindings"] == [
        {"slot_name": "camera", "asset_id": str(asset_id)},
    ]
    assert body["parameter_overrides"] == {}
    assert body["registered_at"] is not None


@pytest.mark.contract
def test_get_fixture_returns_404_for_unknown_fixture() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/fixtures/{uuid4()}")
    assert response.status_code == 404, response.text
