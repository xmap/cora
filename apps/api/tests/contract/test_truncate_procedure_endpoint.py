"""Contract tests for `POST /procedures/{procedure_id}/truncate`.

Action endpoint with `reason` body + optional `interrupted_at`,
204 on success. Covers happy path (after register + start) plus
error surfaces: 400 whitespace-only reason, 400 future
interrupted_at, 404, 409 from-Defined, 409 re-truncate, 422
missing/too-long reason or malformed id.
"""

from datetime import UTC, datetime, timedelta
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
def test_post_truncate_returns_204_for_running_procedure() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(
            f"/procedures/{pid}/truncate",
            json={"reason": "weekend power loss"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_truncate_marks_status_truncated_visible_via_get() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        client.post(f"/procedures/{pid}/truncate", json={"reason": "vacuum loss"})
        response = client.get(f"/procedures/{pid}")
    assert response.json()["status"] == "Truncated"


@pytest.mark.contract
def test_post_truncate_accepts_optional_interrupted_at() -> None:
    interrupted_at = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(
            f"/procedures/{pid}/truncate",
            json={"reason": "weekend crash", "interrupted_at": interrupted_at},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_truncate_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/procedures/{uuid4()}/truncate", json={"reason": "x"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_truncate_returns_409_for_defined_procedure() -> None:
    """Truncate requires Running; from Defined raises CannotTruncate."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "X", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        response = client.post(f"/procedures/{pid}/truncate", json={"reason": "test"})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_truncate_returns_409_when_re_truncating() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        first = client.post(f"/procedures/{pid}/truncate", json={"reason": "first"})
        second = client.post(f"/procedures/{pid}/truncate", json={"reason": "second"})
    assert first.status_code == 204
    assert second.status_code == 409


@pytest.mark.contract
def test_post_truncate_returns_400_for_whitespace_only_reason() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/truncate", json={"reason": "   "})
    assert response.status_code == 400


@pytest.mark.contract
def test_post_truncate_returns_400_for_future_interrupted_at() -> None:
    """interrupted_at must not be in the future; the decider raises 400."""
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(
            f"/procedures/{pid}/truncate",
            json={"reason": "x", "interrupted_at": future},
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_truncate_returns_422_for_missing_reason() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/truncate", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_truncate_returns_422_for_too_long_reason() -> None:
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        response = client.post(f"/procedures/{pid}/truncate", json={"reason": "x" * 501})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_truncate_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures/not-a-uuid/truncate", json={"reason": "x"})
    assert response.status_code == 422
