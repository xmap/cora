"""Contract tests for `POST /procedures/{procedure_id}/iterations/end`.

Action endpoint with an `iteration_index` (+ optional `converged` /
`reason`) body, 204 on success. Covers the happy path (after an
iteration is opened), the open-marker clearing visible via GET, and the
error surfaces: 404, 409 (no open iteration, index mismatch), 422.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_start_open(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "2-BM center alignment", "kind": "center_alignment"}
    pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
    assert client.post(f"/procedures/{pid}/start").status_code == 204
    opened = client.post(f"/procedures/{pid}/iterations/start", json={"iteration_index": 1})
    assert opened.status_code == 204
    return pid


@pytest.mark.contract
def test_post_end_iteration_returns_204_with_verdict() -> None:
    with TestClient(create_app()) as client:
        pid = _register_start_open(client)
        response = client.post(
            f"/procedures/{pid}/iterations/end",
            json={"iteration_index": 1, "converged": True, "reason": "within tolerance"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_end_iteration_returns_204_with_omitted_verdict() -> None:
    with TestClient(create_app()) as client:
        pid = _register_start_open(client)
        response = client.post(f"/procedures/{pid}/iterations/end", json={"iteration_index": 1})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_end_iteration_clears_open_marker_keeps_count_visible_via_get() -> None:
    with TestClient(create_app()) as client:
        pid = _register_start_open(client)
        client.post(
            f"/procedures/{pid}/iterations/end",
            json={"iteration_index": 1, "converged": False},
        )
        body = client.get(f"/procedures/{pid}").json()
    assert body["current_iteration_index"] is None
    assert body["iteration_count"] == 1


@pytest.mark.contract
def test_post_end_then_start_next_iteration_increments_count() -> None:
    with TestClient(create_app()) as client:
        pid = _register_start_open(client)
        client.post(
            f"/procedures/{pid}/iterations/end",
            json={"iteration_index": 1, "converged": False},
        )
        client.post(f"/procedures/{pid}/iterations/start", json={"iteration_index": 2})
        body = client.get(f"/procedures/{pid}").json()
    assert body["iteration_count"] == 2
    assert body["current_iteration_index"] == 2


@pytest.mark.contract
def test_post_end_iteration_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/procedures/{uuid4()}/iterations/end", json={"iteration_index": 1})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_end_iteration_returns_409_when_no_iteration_open() -> None:
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "X", "kind": "center_alignment"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        client.post(f"/procedures/{pid}/start")
        response = client.post(f"/procedures/{pid}/iterations/end", json={"iteration_index": 1})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_end_iteration_returns_409_for_index_mismatch() -> None:
    with TestClient(create_app()) as client:
        pid = _register_start_open(client)  # iteration 1 open
        response = client.post(f"/procedures/{pid}/iterations/end", json={"iteration_index": 2})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_end_iteration_returns_400_for_whitespace_only_reason() -> None:
    """Whitespace-only reason passes Pydantic min_length=1 but the decider
    rejects it after trimming (InvalidProcedureIterationEndReasonError -> 400),
    matching abort / truncate."""
    with TestClient(create_app()) as client:
        pid = _register_start_open(client)
        response = client.post(
            f"/procedures/{pid}/iterations/end",
            json={"iteration_index": 1, "reason": "   "},
        )
    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.contract
def test_post_end_iteration_returns_422_for_too_long_reason() -> None:
    with TestClient(create_app()) as client:
        pid = _register_start_open(client)
        response = client.post(
            f"/procedures/{pid}/iterations/end",
            json={"iteration_index": 1, "reason": "x" * 501},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_end_iteration_returns_422_for_missing_index() -> None:
    with TestClient(create_app()) as client:
        pid = _register_start_open(client)
        response = client.post(f"/procedures/{pid}/iterations/end", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_end_iteration_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures/not-a-uuid/iterations/end", json={"iteration_index": 1})
    assert response.status_code == 422
