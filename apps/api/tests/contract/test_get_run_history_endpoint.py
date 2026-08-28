"""Contract tests for `GET /runs/{run_id}/history`."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset


def _setup_full_run(client: TestClient) -> str:
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    capability_id = create_capability_via_api(client)
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "M",
            "capability_id": capability_id,
            "needed_family_ids": [cap_id],
        },
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "A", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "test"}
    )
    return client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]


@pytest.mark.contract
def test_get_run_history_returns_200_with_started_event_for_sample_run() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.get(f"/runs/{run_id}/history")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["name"] == "32-ID FlyScan"
    assert body["status"] == "Running"
    assert len(body["events"]) == 1
    assert body["events"][0]["event_type"] == "RunStarted"
    assert body["observations"] == []
    assert body["observations_truncated"] is False


@pytest.mark.contract
def test_get_run_history_returns_observations_appended_through_the_api() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(
            f"/runs/{run_id}/observations",
            json={
                "entries": [
                    {
                        "event_id": str(uuid4()),
                        "channel_name": "images",
                        "value": 42.0,
                        "sampled_at": datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC).isoformat(),
                        "sampling_procedure": "monitor",
                    }
                ]
            },
        )
        response = client.get(f"/runs/{run_id}/history")

    body = response.json()
    assert len(body["observations"]) == 1
    assert body["observations"][0]["channel_name"] == "images"
    assert body["observations"][0]["value"] == 42.0


@pytest.mark.contract
def test_get_run_history_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/runs/{uuid4()}/history")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_run_history_returns_422_for_malformed_run_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/runs/not-a-uuid/history")
    assert response.status_code == 422
