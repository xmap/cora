"""Contract tests for `POST /assets/{asset_id}/enter-maintenance`.

Single-source guard (Active -> Maintenance). Mirrors the
activate_asset endpoint contract tests but exercises the maintenance
entry path.
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


def _register_and_activate(client: TestClient) -> str:
    asset_id = _register_asset(client)
    activated = client.post(f"/assets/{asset_id}/activate")
    assert activated.status_code == 204
    return asset_id


@pytest.mark.contract
def test_post_enter_asset_maintenance_returns_204_from_active_state() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_and_activate(client)
        response = client.post(f"/assets/{asset_id}/enter-maintenance")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_enter_asset_maintenance_returns_404_when_asset_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/assets/{missing_id}/enter-maintenance")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert missing_id in body["detail"]


@pytest.mark.contract
def test_post_enter_asset_maintenance_returns_409_when_commissioned() -> None:
    """Pre-service Commissioned assets cannot enter maintenance."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(f"/assets/{asset_id}/enter-maintenance")
    assert response.status_code == 409
    body = response.json()
    assert "Commissioned" in body["detail"]
    assert "Active" in body["detail"]


@pytest.mark.contract
def test_post_enter_asset_maintenance_returns_409_when_already_in_maintenance() -> None:
    """Strict semantics: re-entering raises 409."""
    with TestClient(create_app()) as client:
        asset_id = _register_and_activate(client)
        first = client.post(f"/assets/{asset_id}/enter-maintenance")
        assert first.status_code == 204
        second = client.post(f"/assets/{asset_id}/enter-maintenance")
    assert second.status_code == 409
    assert "Maintenance" in second.json()["detail"]


@pytest.mark.contract
def test_post_enter_asset_maintenance_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/assets/not-a-uuid/enter-maintenance")
    assert response.status_code == 422


@pytest.mark.contract
def test_post_enter_asset_maintenance_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_and_activate(client)
        response = client.post(
            f"/assets/{asset_id}/enter-maintenance",
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
