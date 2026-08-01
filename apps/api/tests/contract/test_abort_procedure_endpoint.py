"""Contract tests for `POST /procedures/{procedure_id}/abort`.

Action endpoint with `reason` body, 204 on success. Covers happy path
(after register + start) plus error surfaces: 400 whitespace-only
reason, 404, 409 from-Defined, 409 re-abort, 422 missing/too-long
reason or malformed id.
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


@pytest.mark.contract
def test_post_abort_returns_204_for_running_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/abort", json={"reason": "vacuum loss"})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_abort_marks_status_aborted_visible_via_get() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        client.post(f"/procedures/{pid}/abort", json={"reason": "quench"})
        response = client.get(f"/procedures/{pid}")
    assert response.json()["status"] == "Aborted"


@pytest.mark.contract
def test_post_abort_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/procedures/{uuid4()}/abort", json={"reason": "x"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_abort_returns_409_for_defined_procedure() -> None:
    """Abort requires Running; from Defined raises CannotAbort."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "X", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        response = client.post(f"/procedures/{pid}/abort", json={"reason": "test"})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_abort_returns_409_when_re_aborting() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        first = client.post(f"/procedures/{pid}/abort", json={"reason": "first"})
        second = client.post(f"/procedures/{pid}/abort", json={"reason": "second"})
    assert first.status_code == 204
    assert second.status_code == 409


@pytest.mark.contract
def test_post_abort_returns_400_for_whitespace_only_reason() -> None:
    """Whitespace-only slips past Pydantic min_length=1 (the trim happens in the VO);
    the domain VO rejects with InvalidProcedureAbortReasonError -> 400."""
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/abort", json={"reason": "   "})
    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.contract
def test_post_abort_returns_422_for_missing_reason() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/abort", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_abort_returns_422_for_empty_reason() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/abort", json={"reason": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_abort_returns_422_for_too_long_reason() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/abort", json={"reason": "x" * 501})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_abort_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures/not-a-uuid/abort", json={"reason": "x"})
    assert response.status_code == 422
