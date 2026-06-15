"""Contract tests for `POST /assemblies/{assembly_id}/fixtures`.

Covers happy-path 201, 404 on unknown Assembly, 404 on unknown Asset,
409 on Deprecated Assembly, 400 on slot cardinality + family mismatch
(application-domain validation errors are wired through
`_handle_validation_error`, which returns 400).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_family(client: TestClient, name: str = "Detector") -> UUID:
    response = client.post(
        "/families",
        json={"name": name, "affordances": []},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["family_id"])


def _register_asset(client: TestClient, family_id: UUID, *, name: str = "Camera-1") -> UUID:
    body: dict[str, object] = {"name": name, "tier": "Device", "parent_id": str(uuid4())}
    create = client.post("/assets", json=body)
    assert create.status_code == 201, create.text
    asset_id = UUID(create.json()["asset_id"])
    add_family = client.post(
        f"/assets/{asset_id}/add-family",
        json={"family_id": str(family_id)},
    )
    assert add_family.status_code == 204, add_family.text
    return asset_id


def _define_assembly_with_one_camera_slot(
    client: TestClient, family_id: UUID, *, name: str = "Microscope"
) -> UUID:
    body = {
        "name": name,
        "required_slots": [
            {
                "slot_name": "camera",
                "required_family_ids": [str(family_id)],
                "cardinality": "Exactly1",
            }
        ],
        "required_wires": [],
    }
    response = client.post("/assemblies", json=body)
    assert response.status_code == 201, response.text
    return UUID(response.json()["assembly_id"])


@pytest.mark.contract
def test_post_fixtures_returns_201_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/fixtures",
            json={
                "slot_asset_bindings": [
                    {"slot_name": "camera", "asset_id": str(asset_id)},
                ],
                "parameter_overrides": {},
            },
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "fixture_id" in body
    UUID(body["fixture_id"])  # parses as a UUID


@pytest.mark.contract
def test_post_fixtures_returns_404_for_unknown_assembly() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assemblies/{uuid4()}/fixtures",
            json={"slot_asset_bindings": [], "parameter_overrides": {}},
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_fixtures_returns_404_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/fixtures",
            json={
                "slot_asset_bindings": [
                    {"slot_name": "camera", "asset_id": str(uuid4())},
                ],
                "parameter_overrides": {},
            },
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_fixtures_returns_409_for_deprecated_assembly() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        deprecate = client.post(
            f"/assemblies/{assembly_id}/deprecate",
            json={"reason": "end-of-life"},
        )
        assert deprecate.status_code == 204, deprecate.text
        response = client.post(
            f"/assemblies/{assembly_id}/fixtures",
            json={
                "slot_asset_bindings": [
                    {"slot_name": "camera", "asset_id": str(asset_id)},
                ],
                "parameter_overrides": {},
            },
        )
    assert response.status_code == 409, response.text
    assert "Deprecated" in response.json()["detail"]


@pytest.mark.contract
def test_post_fixtures_returns_400_for_cardinality_violation() -> None:
    """Exactly1 slot with zero bindings -> 400 mapping incomplete."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/fixtures",
            json={"slot_asset_bindings": [], "parameter_overrides": {}},
        )
    assert response.status_code == 400, response.text


@pytest.mark.contract
def test_post_fixtures_returns_400_for_family_mismatch() -> None:
    """Asset's family_ids do not intersect slot's required_family_ids."""
    with TestClient(create_app()) as client:
        camera_family = _define_family(client, name="Camera")
        rotary_family = _define_family(client, name="Rotary")
        # Asset belongs to rotary, slot wants camera.
        rotary_asset = _register_asset(client, rotary_family, name="Rotary-1")
        assembly_id = _define_assembly_with_one_camera_slot(client, camera_family)
        response = client.post(
            f"/assemblies/{assembly_id}/fixtures",
            json={
                "slot_asset_bindings": [
                    {"slot_name": "camera", "asset_id": str(rotary_asset)},
                ],
                "parameter_overrides": {},
            },
        )
    assert response.status_code == 400, response.text


@pytest.mark.contract
def test_post_fixtures_idempotency_key_returns_same_fixture_id() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        headers = {"Idempotency-Key": "ik-1"}
        body: dict[str, object] = {
            "slot_asset_bindings": [
                {"slot_name": "camera", "asset_id": str(asset_id)},
            ],
            "parameter_overrides": {},
        }
        r1 = client.post(
            f"/assemblies/{assembly_id}/fixtures",
            json=body,
            headers=headers,
        )
        r2 = client.post(
            f"/assemblies/{assembly_id}/fixtures",
            json=body,
            headers=headers,
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["fixture_id"] == r2.json()["fixture_id"]
