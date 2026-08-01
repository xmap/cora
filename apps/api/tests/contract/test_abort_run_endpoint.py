"""Contract tests for `POST /runs/{run_id}/abort`.

Multi-source emergency-exit terminal: `Running | Held -> Aborted`
(source set widened to include Held). Body carries `reason` (1-500 chars).
Re-aborting or aborting from Completed / Stopped raises 409.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import seed_run_upstream_chain


@pytest.mark.contract
def test_post_abort_run_returns_204_from_running_state() -> None:
    with TestClient(create_app()) as client:
        run_id = seed_run_upstream_chain(client)
        response = client.post(
            f"/runs/{run_id}/abort",
            json={"reason": "detector overheating", "justification": "operator: aborting for test"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_abort_run_round_trips_into_get_run_response() -> None:
    """End-to-end: abort + get → status=Aborted."""
    with TestClient(create_app()) as client:
        run_id = seed_run_upstream_chain(client)
        client.post(
            f"/runs/{run_id}/abort",
            json={
                "reason": "beam dump unscheduled",
                "justification": "operator: aborting for test",
            },
        )
        response = client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "Aborted"


@pytest.mark.contract
def test_post_abort_run_returns_204_from_held_state() -> None:
    """6f-3 widens the source set to include Held."""
    with TestClient(create_app()) as client:
        run_id = seed_run_upstream_chain(client)
        client.post(f"/runs/{run_id}/hold")
        response = client.post(
            f"/runs/{run_id}/abort",
            json={
                "reason": "emergency during hold",
                "justification": "operator: aborting for test",
            },
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_abort_run_returns_404_when_run_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/runs/{missing_id}/abort",
            json={"reason": "X", "justification": "operator: aborting for test"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_abort_run_returns_409_when_already_aborted() -> None:
    """Strict-not-idempotent: re-aborting raises 409."""
    with TestClient(create_app()) as client:
        run_id = seed_run_upstream_chain(client)
        first = client.post(
            f"/runs/{run_id}/abort",
            json={"reason": "first abort", "justification": "operator: aborting for test"},
        )
        assert first.status_code == 204
        second = client.post(
            f"/runs/{run_id}/abort",
            json={"reason": "second abort", "justification": "operator: aborting for test"},
        )
    assert second.status_code == 409
    assert "Running" in second.json()["detail"]


@pytest.mark.contract
def test_post_abort_run_returns_409_when_completed() -> None:
    """Cannot abort a Completed Run."""
    with TestClient(create_app()) as client:
        run_id = seed_run_upstream_chain(client)
        complete = client.post(f"/runs/{run_id}/complete")
        assert complete.status_code == 204
        response = client.post(
            f"/runs/{run_id}/abort",
            json={"reason": "X", "justification": "operator: aborting for test"},
        )
    assert response.status_code == 409
    assert "Completed" in response.json()["detail"]


@pytest.mark.contract
def test_post_abort_run_without_justification_returns_422() -> None:
    """Obligation gate (Gate III): an abort with no justification is refused 422
    (fail-closed), even on an otherwise-valid Running run."""
    with TestClient(create_app()) as client:
        run_id = seed_run_upstream_chain(client)
        response = client.post(f"/runs/{run_id}/abort", json={"reason": "detector overheating"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_abort_run_with_blank_justification_returns_422() -> None:
    """A whitespace-only justification passes Pydantic min but the decider trims
    and rejects it (fail-closed obligation gate)."""
    with TestClient(create_app()) as client:
        run_id = seed_run_upstream_chain(client)
        response = client.post(
            f"/runs/{run_id}/abort",
            json={"reason": "detector overheating", "justification": "   "},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_abort_run_rejects_empty_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        run_id = seed_run_upstream_chain(client)
        # Valid justification so this isolates the reason validation, not the gate.
        response = client.post(f"/runs/{run_id}/abort", json={"reason": "", "justification": "j"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_abort_run_rejects_whitespace_only_reason_with_400() -> None:
    """Whitespace passes Pydantic but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        run_id = seed_run_upstream_chain(client)
        response = client.post(
            f"/runs/{run_id}/abort",
            json={"reason": "   ", "justification": "operator: aborting for test"},
        )
    assert response.status_code == 400
    assert "abort reason" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_abort_run_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        run_id = seed_run_upstream_chain(client)
        response = client.post(
            f"/runs/{run_id}/abort", json={"reason": "x" * 501, "justification": "j"}
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_abort_run_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/runs/not-a-uuid/abort", json={"reason": "X", "justification": "j"})
    assert response.status_code == 422
