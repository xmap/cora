"""Contract tests for `POST /assets/{id}/remove-owner`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset_with_owner(client: TestClient, owner_name: str = "HZB") -> str:
    response = client.post(
        "/assets",
        json={
            "name": "Detector-X",
            "tier": "Device",
            "parent_id": str(uuid4()),
            "owners": [{"name": owner_name}],
        },
    )
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["asset_id"]
    return asset_id


@pytest.mark.contract
def test_remove_asset_owner_route_204_on_success() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset_with_owner(client)
        response = client.post(
            f"/assets/{asset_id}/remove-owner",
            json={"owner_name": "HZB"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_remove_asset_owner_route_404_when_owner_not_found() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset_with_owner(client, owner_name="APS")
        response = client.post(
            f"/assets/{asset_id}/remove-owner",
            json={"owner_name": "HZB"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_remove_asset_owner_route_409_when_decommissioned() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset_with_owner(client)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(
            f"/assets/{asset_id}/remove-owner",
            json={"owner_name": "HZB"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_remove_asset_owner_route_404_when_asset_not_found() -> None:
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/{'assets'}/{missing}/remove-owner",
            json={"owner_name": "HZB"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_remove_asset_owner_route_allows_removing_last_owner() -> None:
    """Lock 7: aggregate cardinality is 0-n; removing the last owner
    is not an error."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset_with_owner(client)
        response = client.post(
            f"/assets/{asset_id}/remove-owner",
            json={"owner_name": "HZB"},
        )
    assert response.status_code == 204
