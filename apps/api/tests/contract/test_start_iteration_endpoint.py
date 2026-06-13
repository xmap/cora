"""Contract tests for `POST /procedures/{procedure_id}/iterations/start`.

Action endpoint with an `iteration_index` body, 204 on success. Covers
the happy path (after register + start), the iteration_count denorm
becoming visible via GET, and the error surfaces: 404, 409 (non-Running,
already-open, non-sequential index), 422 (missing / out-of-range body,
malformed id).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "2-BM center alignment", "kind": "center_alignment"}
    return UUID(client.post("/procedures", json=body).json()["procedure_id"])


def _register_and_start(client: TestClient) -> UUID:
    pid = _register(client)
    assert client.post(f"/procedures/{pid}/start").status_code == 204
    return pid


@pytest.mark.contract
def test_post_start_iteration_returns_204_for_running_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/iterations/start", json={"iteration_index": 1})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_start_iteration_bumps_iteration_count_visible_via_get() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        client.post(f"/procedures/{pid}/iterations/start", json={"iteration_index": 1})
        body = client.get(f"/procedures/{pid}").json()
    assert body["iteration_count"] == 1
    assert body["current_iteration_index"] == 1


@pytest.mark.contract
def test_post_start_iteration_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/procedures/{uuid4()}/iterations/start", json={"iteration_index": 1}
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_start_iteration_returns_409_for_defined_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register(client)  # not started
        response = client.post(f"/procedures/{pid}/iterations/start", json={"iteration_index": 1})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_start_iteration_returns_409_when_iteration_already_open() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        first = client.post(f"/procedures/{pid}/iterations/start", json={"iteration_index": 1})
        second = client.post(f"/procedures/{pid}/iterations/start", json={"iteration_index": 2})
    assert first.status_code == 204
    assert second.status_code == 409


@pytest.mark.contract
def test_post_start_iteration_returns_409_for_non_sequential_index() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/iterations/start", json={"iteration_index": 2})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_start_iteration_returns_422_for_missing_index() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/iterations/start", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_start_iteration_returns_422_for_zero_index() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/iterations/start", json={"iteration_index": 0})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_start_iteration_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/procedures/not-a-uuid/iterations/start", json={"iteration_index": 1}
        )
    assert response.status_code == 422
