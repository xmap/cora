"""Contract tests for `POST /assets/{asset_id}/attach-to-fixture`.

Covers happy-path 204, 404 on unknown Asset, 404 on unknown Fixture,
409 on double-attach, 409 on Decommissioned Asset, 400 on phantom
back-reference (Asset not in Fixture.slot_asset_bindings).
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
    client: TestClient, family_id: UUID, *, name: str = "MCTOptics"
) -> UUID:
    body = {
        "name": name,
        "presents_as_family_id": str(family_id),
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


def _register_fixture(client: TestClient, assembly_id: UUID, asset_id: UUID) -> UUID:
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
    return UUID(response.json()["fixture_id"])


@pytest.mark.contract
def test_post_attach_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        fixture_id = _register_fixture(client, assembly_id, asset_id)
        response = client.post(
            f"/assets/{asset_id}/attach-to-fixture",
            json={"fixture_id": str(fixture_id)},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_attach_returns_404_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{uuid4()}/attach-to-fixture",
            json={"fixture_id": str(uuid4())},
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_attach_returns_404_for_unknown_fixture() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        response = client.post(
            f"/assets/{asset_id}/attach-to-fixture",
            json={"fixture_id": str(uuid4())},
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_attach_returns_409_for_double_attach() -> None:
    """Strict-not-idempotent: re-attaching raises 409."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        fixture_id = _register_fixture(client, assembly_id, asset_id)
        first = client.post(
            f"/assets/{asset_id}/attach-to-fixture",
            json={"fixture_id": str(fixture_id)},
        )
        assert first.status_code == 204, first.text
        second = client.post(
            f"/assets/{asset_id}/attach-to-fixture",
            json={"fixture_id": str(fixture_id)},
        )
    assert second.status_code == 409, second.text
    assert "already attached" in second.json()["detail"]


@pytest.mark.contract
def test_post_attach_returns_409_for_decommissioned_asset() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        fixture_id = _register_fixture(client, assembly_id, asset_id)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204, decom.text
        response = client.post(
            f"/assets/{asset_id}/attach-to-fixture",
            json={"fixture_id": str(fixture_id)},
        )
    assert response.status_code == 409, response.text


@pytest.mark.contract
def test_post_attach_returns_400_for_phantom_back_reference() -> None:
    """Asset not in Fixture.slot_asset_bindings -> 400."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        bound_asset_id = _register_asset(client, family_id, name="Bound")
        other_asset_id = _register_asset(client, family_id, name="Other")
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        # Fixture registered with bound_asset_id, NOT other_asset_id.
        fixture_id = _register_fixture(client, assembly_id, bound_asset_id)
        response = client.post(
            f"/assets/{other_asset_id}/attach-to-fixture",
            json={"fixture_id": str(fixture_id)},
        )
    assert response.status_code == 400, response.text
    assert "does not appear" in response.json()["detail"]
