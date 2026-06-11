"""Contract tests for `POST /assets/{asset_id}/activate`.

Mirrors Subject's `test_mount_subject_endpoint.py`. Each test
registers an asset via the existing endpoint, then exercises the
activate transition + its error mappings.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(client: TestClient, name: str = "APS-2BM") -> str:
    """Helper: register a Unit-tier asset under a synthetic parent."""
    response = client.post(
        "/assets",
        json={"name": name, "tier": "Unit", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201
    asset_id: str = response.json()["asset_id"]
    return asset_id


@pytest.mark.contract
def test_post_activate_returns_204_on_first_activation() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(f"/assets/{asset_id}/activate")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_activate_returns_404_when_asset_does_not_exist() -> None:
    """AssetNotFoundError -> 404 via the BC's exception handler."""
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/assets/{missing_id}/activate")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert missing_id in body["detail"]


@pytest.mark.contract
def test_post_activate_returns_409_when_already_active() -> None:
    """Strict semantics: re-activate raises AssetCannotActivateError -> 409."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(f"/assets/{asset_id}/activate")
        assert first.status_code == 204
        second = client.post(f"/assets/{asset_id}/activate")
    assert second.status_code == 409
    body = second.json()
    assert "Active" in body["detail"]
    assert "Commissioned" in body["detail"]


@pytest.mark.contract
def test_post_activate_rejects_invalid_path_uuid_with_422() -> None:
    """Pydantic UUID parsing on path param."""
    with TestClient(create_app()) as client:
        response = client.post("/assets/not-a-uuid/activate")
    assert response.status_code == 422


@pytest.mark.contract
def test_post_activate_with_x_principal_id_header_succeeds() -> None:
    """X-Principal-Id header flows through update-style routes too."""
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/activate",
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
