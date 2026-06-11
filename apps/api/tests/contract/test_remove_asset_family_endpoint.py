"""Contract tests for `POST /assets/{asset_id}/remove-family`.

Mirror of test_add_asset_family_endpoint.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_and_add_family(client: TestClient, family_id: str) -> str:
    asset_response = client.post(
        "/assets",
        json={"name": "APS-2BM", "tier": "Unit", "parent_id": str(uuid4())},
    )
    assert asset_response.status_code == 201
    asset_id: str = asset_response.json()["asset_id"]
    add_response = client.post(
        f"/assets/{asset_id}/add-family",
        json={"family_id": family_id},
    )
    assert add_response.status_code == 204
    return asset_id


@pytest.mark.contract
def test_post_remove_family_returns_204_on_happy_path() -> None:
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_and_add_family(client, cap)
        response = client.post(
            f"/assets/{asset_id}/remove-family",
            json={"family_id": cap},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_remove_family_drops_family_from_get_asset_response() -> None:
    """End-to-end: add then remove leaves family_ids back at empty
    in the read response."""
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_and_add_family(client, cap)
        client.post(f"/assets/{asset_id}/remove-family", json={"family_id": cap})
        response = client.get(f"/assets/{asset_id}")

    assert response.status_code == 200
    assert response.json()["family_ids"] == []


@pytest.mark.contract
def test_post_remove_family_returns_404_when_asset_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing_id}/remove-family",
            json={"family_id": str(uuid4())},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_remove_family_returns_409_when_family_not_present() -> None:
    """Strict-not-idempotent: removing a family not in the set raises."""
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        # Register but don't add the family.
        asset_response = client.post(
            "/assets",
            json={"name": "APS-2BM", "tier": "Unit", "parent_id": str(uuid4())},
        )
        asset_id: str = asset_response.json()["asset_id"]
        response = client.post(f"/assets/{asset_id}/remove-family", json={"family_id": cap})
    assert response.status_code == 409
    assert "not in" in response.json()["detail"]


@pytest.mark.contract
def test_post_remove_family_returns_409_when_asset_is_decommissioned() -> None:
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_and_add_family(client, cap)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(f"/assets/{asset_id}/remove-family", json={"family_id": cap})
    assert response.status_code == 409
    assert "Decommissioned" in response.json()["detail"]


@pytest.mark.contract
def test_post_remove_family_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets/not-a-uuid/remove-family",
            json={"family_id": str(uuid4())},
        )
    assert response.status_code == 422
