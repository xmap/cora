"""Contract tests for `POST /assets/{asset_id}/degrade`.

Action endpoint with body `{reason}`. Target-state semantics:
any condition -> Degraded. No-op when already Degraded.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(client: TestClient) -> str:
    response = client.post(
        "/assets",
        json={"name": "Detector-Oryx", "tier": "Device", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["asset_id"]
    return asset_id


@pytest.mark.contract
def test_post_degrade_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/degrade",
            json={"reason": "hot pixel detected"},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_degrade_returns_204_when_already_degraded() -> None:
    """No-op-on-unchanged: second call still returns 204 (the decider
    returns [] but the route happily reports success)."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(f"/assets/{asset_id}/degrade", json={"reason": "first"})
        assert first.status_code == 204
        second = client.post(f"/assets/{asset_id}/degrade", json={"reason": "second"})
    assert second.status_code == 204


@pytest.mark.contract
def test_post_degrade_returns_404_when_asset_missing() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing_id}/degrade",
            json={"reason": "missing"},
        )
    assert response.status_code == 404
    assert missing_id in response.json()["detail"]


@pytest.mark.contract
def test_post_degrade_rejects_empty_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/degrade",
            json={"reason": ""},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_degrade_rejects_oversized_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/degrade",
            json={"reason": "x" * 501},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_degrade_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets/not-a-uuid/degrade",
            json={"reason": "x"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_degrade_works_in_decommissioned_lifecycle() -> None:
    """Condition transitions are independent of lifecycle: a
    Decommissioned asset can still be marked Degraded (honest about
    device-state-in-storage)."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(
            f"/assets/{asset_id}/degrade",
            json={"reason": "discovered fault on inventory check"},
        )
    assert response.status_code == 204
