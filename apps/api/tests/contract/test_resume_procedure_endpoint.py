"""Contract tests for `POST /procedures/{procedure_id}/resume`.

Action endpoint with `re_establishment_boundary` body, 204 on success.
Covers happy path (register + start + hold) plus error surfaces: 404,
409 from-Running (not Held), 422 missing / negative boundary, 422
malformed id.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_start_hold(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "Vessel-A bakeout", "kind": "bakeout"}
    pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
    assert client.post(f"/procedures/{pid}/start").status_code == 204
    assert (
        client.post(f"/procedures/{pid}/hold", json={"reason": "beam dropped"}).status_code == 204
    )
    return pid


@pytest.mark.contract
def test_post_resume_returns_204_for_held_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register_start_hold(client)
        response = client.post(f"/procedures/{pid}/resume", json={"re_establishment_boundary": 0})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_resume_marks_status_running_visible_via_get() -> None:
    with TestClient(create_app()) as client:
        pid = _register_start_hold(client)
        client.post(f"/procedures/{pid}/resume", json={"re_establishment_boundary": 1})
        response = client.get(f"/procedures/{pid}")
    assert response.json()["status"] == "Running"


@pytest.mark.contract
def test_post_resume_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/procedures/{uuid4()}/resume", json={"re_establishment_boundary": 0}
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_resume_returns_409_for_running_procedure() -> None:
    """Resume requires Held; from Running (never held) raises CannotResume."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "X", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        client.post(f"/procedures/{pid}/start")
        response = client.post(f"/procedures/{pid}/resume", json={"re_establishment_boundary": 0})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_resume_returns_422_for_missing_boundary() -> None:
    with TestClient(create_app()) as client:
        pid = _register_start_hold(client)
        response = client.post(f"/procedures/{pid}/resume", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_resume_returns_422_for_negative_boundary() -> None:
    """Pydantic ge=0 rejects a negative boundary at the wire before the decider."""
    with TestClient(create_app()) as client:
        pid = _register_start_hold(client)
        response = client.post(f"/procedures/{pid}/resume", json={"re_establishment_boundary": -1})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_resume_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/procedures/not-a-uuid/resume", json={"re_establishment_boundary": 0}
        )
    assert response.status_code == 422
