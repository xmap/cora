"""Contract tests for `POST /plans/{plan_id}/version`.

Mirror of `test_version_practice_endpoint.py`. Multi-source guard
(Defined | Versioned -> Versioned).
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def _setup_plan(client: TestClient) -> str:
    _cap_id = create_capability_via_api(client)
    """Seed Family + Method + Practice + Asset (with capability) +
    Plan via the public API; return the plan_id as a string."""
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={"name": "Test Method", "capability_id": _cap_id, "needed_family_ids": [cap_id]},
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
def test_post_version_plan_returns_204_from_defined_state() -> None:
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        response = client.post(
            f"/plans/{plan_id}/version", json={"version_tag": "v2", "affordances": []}
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_version_plan_returns_204_from_versioned_state() -> None:
    """Subsequent revision (Versioned → Versioned)."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        first = client.post(
            f"/plans/{plan_id}/version", json={"version_tag": "v1", "affordances": []}
        )
        assert first.status_code == 204
        second = client.post(
            f"/plans/{plan_id}/version", json={"version_tag": "v2", "affordances": []}
        )
    assert second.status_code == 204


@pytest.mark.contract
def test_post_version_plan_round_trips_into_get_plan_response() -> None:
    """End-to-end: version + get → status=Versioned, version=label."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        client.post(f"/plans/{plan_id}/version", json={"version_tag": "2026-Q3", "affordances": []})
        response = client.get(f"/plans/{plan_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Versioned"
    assert body["version"] == "2026-Q3"


@pytest.mark.contract
def test_post_version_plan_returns_404_when_plan_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/plans/{missing_id}/version", json={"version_tag": "v1", "affordances": []}
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_version_plan_returns_409_when_deprecated() -> None:
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        deprecate = client.post(f"/plans/{plan_id}/deprecate")
        assert deprecate.status_code == 204
        response = client.post(
            f"/plans/{plan_id}/version", json={"version_tag": "v2", "affordances": []}
        )
    assert response.status_code == 409
    assert "Deprecated" in response.json()["detail"]


@pytest.mark.contract
def test_post_version_plan_rejects_empty_version_tag_with_422() -> None:
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        response = client.post(
            f"/plans/{plan_id}/version", json={"version_tag": "", "affordances": []}
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_plan_rejects_whitespace_only_with_400() -> None:
    """Whitespace passes Pydantic but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        response = client.post(
            f"/plans/{plan_id}/version", json={"version_tag": "   ", "affordances": []}
        )
    assert response.status_code == 400
    assert "version tag" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_version_plan_rejects_too_long_with_422() -> None:
    with TestClient(create_app()) as client:
        plan_id = _setup_plan(client)
        response = client.post(f"/plans/{plan_id}/version", json={"version_tag": "v" * 51})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_plan_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/plans/not-a-uuid/version", json={"version_tag": "v1", "affordances": []}
        )
    assert response.status_code == 422
