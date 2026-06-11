"""Contract tests for `POST /assets/{asset_id}/exit-maintenance`.

Single-source guard (Maintenance -> Active). Inverse of
enter_asset_maintenance.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(client: TestClient, name: str = "APS-2BM") -> str:
    response = client.post(
        "/assets",
        json={"name": name, "tier": "Unit", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201
    asset_id: str = response.json()["asset_id"]
    return asset_id


def _drive_to_maintenance(client: TestClient) -> str:
    asset_id = _register_asset(client)
    activated = client.post(f"/assets/{asset_id}/activate")
    assert activated.status_code == 204
    entered = client.post(f"/assets/{asset_id}/enter-maintenance")
    assert entered.status_code == 204
    return asset_id


@pytest.mark.contract
def test_post_exit_returns_204_from_maintenance_state() -> None:
    with TestClient(create_app()) as client:
        asset_id = _drive_to_maintenance(client)
        response = client.post(f"/assets/{asset_id}/exit-maintenance")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_exit_returns_404_when_asset_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/assets/{missing_id}/exit-maintenance")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert missing_id in body["detail"]


@pytest.mark.contract
def test_post_exit_returns_409_when_active() -> None:
    """Strict semantics: exit on already-Active raises."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        client.post(f"/assets/{asset_id}/activate")
        response = client.post(f"/assets/{asset_id}/exit-maintenance")
    assert response.status_code == 409
    body = response.json()
    assert "Active" in body["detail"]
    assert "Maintenance" in body["detail"]


@pytest.mark.contract
def test_post_exit_returns_409_when_commissioned() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(f"/assets/{asset_id}/exit-maintenance")
    assert response.status_code == 409
    assert "Commissioned" in response.json()["detail"]


@pytest.mark.contract
def test_post_exit_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/assets/not-a-uuid/exit-maintenance")
    assert response.status_code == 422


@pytest.mark.contract
def test_post_exit_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _drive_to_maintenance(client)
        response = client.post(
            f"/assets/{asset_id}/exit-maintenance",
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
