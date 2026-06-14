"""Contract tests for `POST /assets/{asset_id}/detach-from-fixture`.

Covers happy-path 204, 404 on unknown Asset, 409 on standalone Asset
(not attached), 409 on wrong fixture_id (defensive guard), happy-path
re-attach after detach.
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


def _register_asset(client: TestClient, family_id: UUID, *, name: str = "Cam-1") -> UUID:
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


def _attach(client: TestClient, asset_id: UUID, fixture_id: UUID) -> None:
    response = client.post(
        f"/assets/{asset_id}/attach-to-fixture",
        json={"fixture_id": str(fixture_id)},
    )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_detach_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        fixture_id = _register_fixture(client, assembly_id, asset_id)
        _attach(client, asset_id, fixture_id)
        response = client.post(
            f"/assets/{asset_id}/detach-from-fixture",
            json={"fixture_id": str(fixture_id)},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_detach_returns_404_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{uuid4()}/detach-from-fixture",
            json={"fixture_id": str(uuid4())},
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_detach_returns_409_for_standalone_asset() -> None:
    """Asset was never attached -> 409 not attached."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        response = client.post(
            f"/assets/{asset_id}/detach-from-fixture",
            json={"fixture_id": str(uuid4())},
        )
    assert response.status_code == 409, response.text
    assert "not attached" in response.json()["detail"]


@pytest.mark.contract
def test_post_detach_returns_409_for_double_detach() -> None:
    """Strict-not-idempotent: a second detach raises 409."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        fixture_id = _register_fixture(client, assembly_id, asset_id)
        _attach(client, asset_id, fixture_id)
        first = client.post(
            f"/assets/{asset_id}/detach-from-fixture",
            json={"fixture_id": str(fixture_id)},
        )
        assert first.status_code == 204, first.text
        second = client.post(
            f"/assets/{asset_id}/detach-from-fixture",
            json={"fixture_id": str(fixture_id)},
        )
    assert second.status_code == 409, second.text
    assert "not attached" in second.json()["detail"]


@pytest.mark.contract
def test_post_detach_returns_409_for_wrong_fixture_id() -> None:
    """Asset is attached but to a different Fixture than the request."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        assembly_id = _define_assembly_with_one_camera_slot(client, family_id)
        fixture_id = _register_fixture(client, assembly_id, asset_id)
        _attach(client, asset_id, fixture_id)
        response = client.post(
            f"/assets/{asset_id}/detach-from-fixture",
            json={"fixture_id": str(uuid4())},
        )
    assert response.status_code == 409, response.text
    assert (
        "different" in response.json()["detail"].lower()
        or "not the requested" in response.json()["detail"]
    )


@pytest.mark.contract
def test_post_detach_then_reattach_to_different_fixture() -> None:
    """After detach, the Asset is free to attach to a DIFFERENT Fixture."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client, family_id)
        # Register two distinct Assemblies + Fixtures both binding this Asset.
        assembly_a = _define_assembly_with_one_camera_slot(client, family_id, name="Microscope-A")
        assembly_b = _define_assembly_with_one_camera_slot(client, family_id, name="Microscope-B")
        fixture_a = _register_fixture(client, assembly_a, asset_id)
        fixture_b = _register_fixture(client, assembly_b, asset_id)
        _attach(client, asset_id, fixture_a)
        # Detach from A.
        detach = client.post(
            f"/assets/{asset_id}/detach-from-fixture",
            json={"fixture_id": str(fixture_a)},
        )
        assert detach.status_code == 204, detach.text
        # Re-attach to B.
        reattach = client.post(
            f"/assets/{asset_id}/attach-to-fixture",
            json={"fixture_id": str(fixture_b)},
        )
    assert reattach.status_code == 204, reattach.text
