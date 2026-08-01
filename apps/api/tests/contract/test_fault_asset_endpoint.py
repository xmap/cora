"""Contract tests for `POST /assets/{asset_id}/fault`.

Action endpoint with body `{reason}`. Target-state semantics:
any condition -> Faulted. No-op when already Faulted.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(client: TestClient) -> str:
    response = client.post(
        "/assets",
        json={"name": "Pump-XDS35i", "tier": "Device", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["asset_id"]
    return asset_id


@pytest.mark.contract
def test_post_fault_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/fault",
            json={"reason": "vacuum pump seized"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_fault_returns_204_when_already_faulted() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(f"/assets/{asset_id}/fault", json={"reason": "first"})
        assert first.status_code == 204
        second = client.post(f"/assets/{asset_id}/fault", json={"reason": "second"})
    assert second.status_code == 204


@pytest.mark.contract
def test_post_fault_returns_404_when_asset_missing() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing_id}/fault",
            json={"reason": "missing"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_fault_rejects_empty_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(f"/assets/{asset_id}/fault", json={"reason": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_fault_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/assets/not-a-uuid/fault", json={"reason": "x"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_fault_after_degrade_succeeds() -> None:
    """Worsening: Degraded -> Faulted via fault_asset."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        deg = client.post(f"/assets/{asset_id}/degrade", json={"reason": "warning"})
        assert deg.status_code == 204
        response = client.post(
            f"/assets/{asset_id}/fault",
            json={"reason": "got worse, total failure"},
        )
    assert response.status_code == 204
