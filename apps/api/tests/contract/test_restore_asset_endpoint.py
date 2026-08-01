"""Contract tests for `POST /assets/{asset_id}/restore`.

Action endpoint with body `{reason}`. Target-state semantics:
any condition -> Nominal. No-op when already Nominal.

Distinct path from `POST /assets/{asset_id}/exit-maintenance`
(which moves lifecycle).
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(client: TestClient) -> str:
    response = client.post(
        "/assets",
        json={"name": "Stage-A3200", "tier": "Device", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["asset_id"]
    return asset_id


@pytest.mark.contract
def test_post_restore_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        # Fault it first so restore has somewhere to come from.
        fault = client.post(f"/assets/{asset_id}/fault", json={"reason": "broken"})
        assert fault.status_code == 204
        response = client.post(
            f"/assets/{asset_id}/restore",
            json={"reason": "replaced flat cable"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_restore_returns_204_when_already_nominal() -> None:
    """No-op-on-unchanged: a fresh asset is already Nominal; restore
    is a no-op but still 204."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(f"/assets/{asset_id}/restore", json={"reason": "redundant call"})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_restore_returns_404_when_asset_missing() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing_id}/restore",
            json={"reason": "missing"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_restore_rejects_empty_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(f"/assets/{asset_id}/restore", json={"reason": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_restore_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/assets/not-a-uuid/restore", json={"reason": "x"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_restore_path_distinct_from_exit_asset_maintenance() -> None:
    """Sanity check: the two endpoints don't collide. Both
    exist, both return 204 on their happy paths, but they target
    different state dimensions."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        # condition restore (fresh asset already Nominal: no-op 204)
        cond = client.post(f"/assets/{asset_id}/restore", json={"reason": "ok"})
        assert cond.status_code == 204
        # lifecycle exit_asset_maintenance from a fresh Commissioned
        # asset must 409 (it requires Maintenance source); both
        # endpoints exist but they aren't routed to the same handler.
        lifecycle = client.post(f"/assets/{asset_id}/exit-maintenance")
        assert lifecycle.status_code == 409
