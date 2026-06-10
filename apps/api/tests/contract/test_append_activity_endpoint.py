"""Contract tests for `POST /procedures/{procedure_id}/activities`.

Action endpoint with `entries` batch body, 200 OK with
`{"event_count": N}` on success. Covers happy path (after register +
start) plus error surfaces: 404 unknown procedure, 409 not-Running,
422 missing/invalid fields, 422 batch-cap.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_and_start(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "Vessel-A bakeout", "kind": "bakeout"}
    pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
    started = client.post(f"/procedures/{pid}/start")
    assert started.status_code == 204
    return pid


def _entry(
    *,
    event_id: UUID | None = None,
    step_kind: str = "setpoint",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_id": str(event_id or uuid4()),
        "step_kind": step_kind,
        "payload": payload or {"channel": "T_oven", "target_value": 423.0},
        "sampled_at": "2026-05-15T12:00:00+00:00",
    }


@pytest.mark.contract
def test_post_steps_returns_200_with_event_count_for_running_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/activities", json={"entries": [_entry()]})
    assert response.status_code == 200
    assert response.json() == {"event_count": 1}


@pytest.mark.contract
def test_post_steps_accepts_polymorphic_batch() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        body = {
            "entries": [
                _entry(step_kind="setpoint"),
                _entry(
                    step_kind="action",
                    payload={"action_name": "open_valve", "params": {"valve": "V12"}},
                ),
                _entry(
                    step_kind="check",
                    payload={"channel": "T_oven", "passed": True, "actual": 422.8},
                ),
            ]
        }
        response = client.post(f"/procedures/{pid}/activities", json=body)
    assert response.status_code == 200
    assert response.json() == {"event_count": 3}


@pytest.mark.contract
def test_post_steps_dedups_silently_on_repeat_event_id() -> None:
    """Producer retry with same event_id is a silent no-op (still 200)."""
    eid = uuid4()
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        first = client.post(
            f"/procedures/{pid}/activities", json={"entries": [_entry(event_id=eid)]}
        )
        second = client.post(
            f"/procedures/{pid}/activities",
            json={"entries": [_entry(event_id=eid, step_kind="action")]},
        )
    assert first.status_code == 200
    assert second.status_code == 200
    # Both report event_count=1 (the count is "accepted by the store",
    # which includes silently-deduped retries per the response-shape doc).
    assert first.json() == {"event_count": 1}
    assert second.json() == {"event_count": 1}


@pytest.mark.contract
def test_post_steps_returns_404_for_unknown_procedure() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/procedures/{uuid4()}/activities", json={"entries": [_entry()]})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_steps_returns_409_for_defined_procedure() -> None:
    """Steps require Running; from Defined raises ProcedureStepsLogbookClosed."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "X", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        # Skip start; Procedure stays Defined.
        response = client.post(f"/procedures/{pid}/activities", json={"entries": [_entry()]})
    assert response.status_code == 409
    assert "closed" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_steps_returns_409_for_completed_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        client.post(f"/procedures/{pid}/complete")
        response = client.post(f"/procedures/{pid}/activities", json={"entries": [_entry()]})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_steps_returns_422_for_invalid_step_kind() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(
            f"/procedures/{pid}/activities",
            json={"entries": [_entry(step_kind="not-a-kind")]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_steps_returns_422_for_empty_batch() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/activities", json={"entries": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_steps_returns_422_for_batch_over_cap() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        # 501 entries exceeds the 500 cap.
        body = {"entries": [_entry() for _ in range(501)]}
        response = client.post(f"/procedures/{pid}/activities", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_steps_returns_422_for_missing_required_field() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        # missing 'sampled_at'
        bad_entry = {
            "event_id": str(uuid4()),
            "step_kind": "setpoint",
            "payload": {"channel": "X"},
        }
        response = client.post(f"/procedures/{pid}/activities", json={"entries": [bad_entry]})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_steps_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures/not-a-uuid/activities", json={"entries": [_entry()]})
    assert response.status_code == 422
