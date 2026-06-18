"""Contract tests for `POST /runs/{run_id}/stop`.

Multi-source controlled-exit terminal: `Running | Held -> Stopped`.
Body carries `reason` (1-500 chars). Re-stopping or stopping from
any terminal raises 409.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset


def _setup_full_run(client: TestClient) -> str:
    _cap_id = create_capability_via_api(client)
    """Seed full upstream chain + start a Run. Returns the run_id."""
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "M",
            "capability_id": _cap_id,
            "needed_family_ids": [cap_id],
        },
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets", json={"name": "A", "tier": "Unit", "parent_id": None, "facility_code": "cora"}
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
    run_id = client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]
    return run_id


@pytest.mark.contract
def test_post_stop_run_returns_204_from_running_state() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(f"/runs/{run_id}/stop", json={"reason": "hit time budget cleanly"})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_stop_run_returns_204_from_held_state() -> None:
    """Multi-source: stop accepts Held."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(f"/runs/{run_id}/hold")
        response = client.post(f"/runs/{run_id}/stop", json={"reason": "ending early during hold"})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_stop_run_round_trips_into_get_run_response() -> None:
    """End-to-end: stop + get → status=Stopped."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(f"/runs/{run_id}/stop", json={"reason": "operator stop"})
        response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "Stopped"


@pytest.mark.contract
def test_post_stop_run_returns_404_when_run_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/runs/{missing_id}/stop", json={"reason": "X"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_stop_run_returns_409_when_already_stopped() -> None:
    """Strict-not-idempotent: re-stopping raises 409."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        first = client.post(f"/runs/{run_id}/stop", json={"reason": "first stop"})
        assert first.status_code == 204
        second = client.post(f"/runs/{run_id}/stop", json={"reason": "second stop"})
    assert second.status_code == 409


@pytest.mark.contract
def test_post_stop_run_returns_409_when_completed() -> None:
    """Cannot stop a Completed Run."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        complete = client.post(f"/runs/{run_id}/complete")
        assert complete.status_code == 204
        response = client.post(f"/runs/{run_id}/stop", json={"reason": "X"})
    assert response.status_code == 409
    assert "Completed" in response.json()["detail"]


@pytest.mark.contract
def test_post_stop_run_returns_409_when_aborted() -> None:
    """Cannot stop an Aborted Run."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(f"/runs/{run_id}/abort", json={"reason": "emergency"})
        response = client.post(f"/runs/{run_id}/stop", json={"reason": "X"})
    assert response.status_code == 409
    assert "Aborted" in response.json()["detail"]


@pytest.mark.contract
def test_post_stop_run_rejects_empty_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(f"/runs/{run_id}/stop", json={"reason": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_stop_run_rejects_whitespace_only_reason_with_400() -> None:
    """Whitespace passes Pydantic but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(f"/runs/{run_id}/stop", json={"reason": "   "})
    assert response.status_code == 400
    assert "stop reason" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_stop_run_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(f"/runs/{run_id}/stop", json={"reason": "x" * 501})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_stop_run_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/runs/not-a-uuid/stop", json={"reason": "X"})
    assert response.status_code == 422
