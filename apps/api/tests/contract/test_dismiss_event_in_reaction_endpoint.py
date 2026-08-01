"""Contract tests for `POST /agent/reactions/{name}/dismiss-event`.

The slice is fundamentally PG-bound (it advances a SQL row on
projection_bookmarks). In the in-memory test app the handler raises
`DismissalRequiresPostgresError` which the BC's exception handler
maps to 503. So the contract layer pins:

  - 422 for schema violations (missing body, malformed UUID, oversize
    reason, missing required fields)
  - 503 for the in-memory-mode rejection

The PG happy path (201 + Decision row + bookmark advance), 404
mappings (subscriber unknown / event unknown), 409 mapping
(already-dismissed), and the 400 mapping (whitespace reason) live in
the integration test against real Postgres, where the SQL state
actually exists.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_dismiss_event_returns_503_in_memory_mode() -> None:
    """In-memory app has no projection_bookmarks table; the handler
    raises DismissalRequiresPostgresError; the route maps to 503."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/agent/reactions/run_debriefer/dismiss-event",
            json={"event_id": str(uuid4()), "reason": "test"},
        )
    assert response.status_code == 503
    assert "postgres" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_dismiss_event_returns_422_for_missing_event_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/agent/reactions/run_debriefer/dismiss-event",
            json={"reason": "missing event_id"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_dismiss_event_returns_422_for_missing_reason() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/agent/reactions/run_debriefer/dismiss-event",
            json={"event_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_dismiss_event_returns_422_for_malformed_event_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/agent/reactions/run_debriefer/dismiss-event",
            json={"event_id": "not-a-uuid", "reason": "test"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_dismiss_event_returns_422_for_empty_reason() -> None:
    """Pydantic `min_length=1` short-circuits the empty string before
    the handler runs; the body is rejected at 422 rather than the
    handler's 400 InvalidDismissalReasonError."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/agent/reactions/run_debriefer/dismiss-event",
            json={"event_id": str(uuid4()), "reason": ""},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_dismiss_event_returns_422_for_oversize_reason() -> None:
    """Pydantic `max_length=500` short-circuits the oversize string
    before the handler runs."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/agent/reactions/run_debriefer/dismiss-event",
            json={"event_id": str(uuid4()), "reason": "x" * 501},
        )
    assert response.status_code == 422
