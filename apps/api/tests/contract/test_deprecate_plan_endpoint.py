"""Contract tests for `POST /plans/{plan_id}/deprecate`.

Mirror of `test_deprecate_practice_endpoint.py`. Multi-source guard
(Defined | Versioned -> Deprecated). Re-deprecating raises 409.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def _setup_plan(client: TestClient) -> str:
    _cap_id = create_capability_via_api(client)
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "Test Method",
            "capability_id": _cap_id,
            "needed_family_ids": [cap_id],
        },
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "TestAsset", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "32-ID FlyScan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    return plan_id


@pytest.mark.contract
def test_post_deprecate_plan_returns_204_from_defined_state() -> None:
    """Direct deprecation (no prior versioning)."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        response = client.post(f"/plans/{plan_id}/deprecate")
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_plan_returns_204_from_versioned_state() -> None:
    """Full lifecycle: define + version + deprecate."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        client.post(f"/plans/{plan_id}/version", json={"version_tag": "v1"})
        response = client.post(f"/plans/{plan_id}/deprecate")
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_plan_round_trips_into_get_plan_response() -> None:
    """End-to-end: deprecate + get → status=Deprecated, version preserved."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        client.post(f"/plans/{plan_id}/version", json={"version_tag": "2026-Q2"})
        client.post(f"/plans/{plan_id}/deprecate")
        response = client.get(f"/plans/{plan_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Deprecated"
    # Audit signal: latest version_tag preserved through deprecation.
    assert body["version"] == "2026-Q2"


@pytest.mark.contract
def test_post_deprecate_plan_returns_404_when_plan_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/plans/{missing_id}/deprecate")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_deprecate_plan_returns_409_when_already_deprecated() -> None:
    """Strict-not-idempotent: re-deprecating raises 409."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        first = client.post(f"/plans/{plan_id}/deprecate")
        assert first.status_code == 204
        second = client.post(f"/plans/{plan_id}/deprecate")
    assert second.status_code == 409
    body = second.json()
    assert "Defined" in body["detail"]
    assert "Versioned" in body["detail"]


@pytest.mark.contract
def test_post_deprecate_plan_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/plans/not-a-uuid/deprecate")
    assert response.status_code == 422
