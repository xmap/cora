"""Contract tests for `POST /procedures/{procedure_id}/diagnostics`.

Action endpoint with `entries` batch body, 200 OK with `{"event_count": N}` on
success. Covers happy path (after register + start) plus error surfaces: 404
unknown procedure, 409 not-Running, 422 missing/invalid fields, 422 batch-cap.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_and_start(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "rotation-center steer", "kind": "characterization"}
    pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
    started = client.post(f"/procedures/{pid}/start")
    assert started.status_code == 204
    return pid


def _entry(*, event_id: UUID | None = None, iteration_index: int = 0) -> dict[str, Any]:
    return {
        "event_id": str(event_id or uuid4()),
        "iteration_index": iteration_index,
        "model_ref": "botorch",
        "payload": {"lengthscale_x": 0.8, "noise": 0.005, "acquisition_value": 0.12},
        "sampled_at": "2026-07-01T12:00:00+00:00",
    }


@pytest.mark.contract
def test_post_diagnostics_returns_200_with_event_count_for_running_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/diagnostics", json={"entries": [_entry()]})
    assert response.status_code == 200
    assert response.json() == {"event_count": 1}


@pytest.mark.contract
def test_post_diagnostics_dedups_silently_on_repeat_event_id() -> None:
    eid = uuid4()
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        first = client.post(
            f"/procedures/{pid}/diagnostics", json={"entries": [_entry(event_id=eid)]}
        )
        second = client.post(
            f"/procedures/{pid}/diagnostics",
            json={"entries": [_entry(event_id=eid, iteration_index=1)]},
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {"event_count": 1}
    assert second.json() == {"event_count": 1}


@pytest.mark.contract
def test_post_diagnostics_returns_404_for_unknown_procedure() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/procedures/{uuid4()}/diagnostics", json={"entries": [_entry()]})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_diagnostics_returns_409_for_defined_procedure() -> None:
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "X", "kind": "characterization"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        response = client.post(f"/procedures/{pid}/diagnostics", json={"entries": [_entry()]})
    assert response.status_code == 409
    assert "closed" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_diagnostics_returns_409_for_completed_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        client.post(f"/procedures/{pid}/complete")
        response = client.post(f"/procedures/{pid}/diagnostics", json={"entries": [_entry()]})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_diagnostics_returns_422_for_empty_batch() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/diagnostics", json={"entries": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_diagnostics_returns_422_for_batch_over_cap() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        body = {"entries": [_entry() for _ in range(501)]}
        response = client.post(f"/procedures/{pid}/diagnostics", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_diagnostics_returns_422_for_missing_required_field() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        bad_entry = {
            "event_id": str(uuid4()),
            "iteration_index": 0,
            "model_ref": "botorch",
            "payload": {"acquisition_value": 0.1},
            # missing 'sampled_at'
        }
        response = client.post(f"/procedures/{pid}/diagnostics", json={"entries": [bad_entry]})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_diagnostics_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures/not-a-uuid/diagnostics", json={"entries": [_entry()]})
    assert response.status_code == 422
