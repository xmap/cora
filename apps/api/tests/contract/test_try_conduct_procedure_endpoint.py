"""Contract tests for `POST /procedures/{procedure_id}/try-conduct`.

Pause-capable conduct: like conduct, but a RECOVERABLE step failure (setpoint
/ check) PAUSES the Procedure to Held (resumable via reconduct) instead of
aborting. Always 200 with the outcome in the body; `held` flags the pause.
404 for an unknown procedure, 422 for a malformed body.

The test wire-up uses `InMemoryControlPort` with no pre-connected addresses,
so a setpoint to any address fails with ControlNotConnectedError: that is the
recoverable failure this slice pauses on.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "Vessel-A bakeout", "kind": "bakeout"}
    return UUID(client.post("/procedures", json=body).json()["procedure_id"])


@pytest.mark.contract
def test_post_try_conduct_empty_steps_completes() -> None:
    """An empty step list starts + completes the Procedure (no failure to pause on)."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        response = client.post(f"/procedures/{pid}/try-conduct", json={"steps": []})
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] is True
    assert body["held"] is False


@pytest.mark.contract
def test_post_try_conduct_recoverable_setpoint_pauses_to_held() -> None:
    """A setpoint to an unconnected address is recoverable: pause to Held, not abort."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        response = client.post(
            f"/procedures/{pid}/try-conduct",
            json={"steps": [{"kind": "setpoint", "address": "2bma:x", "value": 1.0}]},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] is False
    assert body["held"] is True
    assert body["failure"]["source_kind"] == "setpoint"


@pytest.mark.contract
def test_post_try_conduct_action_failure_aborts_not_held() -> None:
    """An unregistered action is an acquisition failure: abort (not held)."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        response = client.post(
            f"/procedures/{pid}/try-conduct",
            json={"steps": [{"kind": "action", "name": "unregistered"}]},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] is False
    assert body["held"] is False
    assert body["failure"]["source_kind"] == "action"


@pytest.mark.contract
def test_post_try_conduct_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/procedures/{uuid4()}/try-conduct", json={"steps": []})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_try_conduct_returns_422_for_unknown_step_kind() -> None:
    with TestClient(create_app()) as client:
        pid = _register(client)
        response = client.post(
            f"/procedures/{pid}/try-conduct",
            json={"steps": [{"kind": "teleport", "address": "x", "value": 1}]},
        )
    assert response.status_code == 422
