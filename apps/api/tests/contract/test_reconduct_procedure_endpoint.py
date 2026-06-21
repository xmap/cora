"""Contract tests for `POST /procedures/{procedure_id}/reconduct`.

Resume-and-replay: resumes a Held Procedure and replays its pinned
step-list tail. 200 with replay outcomes in body; 404/409/422/500 for
protocol / guard / corruption faults.

The 200 happy paths are now API-reachable via `try_conduct_procedure`: it
conducts a Procedure that pauses to `Held` on a recoverable step failure,
leaving the pinned `ResolvedStepsRecorded` for `reconduct` to replay. The
test wire-up uses `InMemoryControlPort` with no pre-connected addresses, so a
setpoint fails (recoverable -> Held); reconduct then replays the pinned tail
from the operator's boundary (an empty tail completes; a tail starting with an
acquisition halts-for-operator).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register(client: TestClient) -> UUID:
    body: dict[str, Any] = {"name": "Vessel-A bakeout", "kind": "bakeout"}
    return UUID(client.post("/procedures", json=body).json()["procedure_id"])


def _try_conduct_to_held(client: TestClient, steps: list[dict[str, Any]]) -> UUID:
    """Register + try-conduct a Procedure to Held (the recoverable setpoint at
    index 0 fails on the unconnected port), leaving a pinned resolved-step list
    `reconduct` can replay. Returns the Held Procedure's id."""
    pid = _register(client)
    held = client.post(f"/procedures/{pid}/try-conduct", json={"steps": steps})
    assert held.status_code == 200
    assert held.json()["held"] is True
    return pid


@pytest.mark.contract
def test_post_reconduct_completes_held_procedure_with_empty_tail() -> None:
    """Reconduct a Held Procedure past the end of its resolved steps (empty
    tail): nothing to replay, so it auto-completes (200, succeeded)."""
    with TestClient(create_app()) as client:
        pid = _try_conduct_to_held(
            client, [{"kind": "setpoint", "address": "2bma:x", "value": 1.0}]
        )
        # boundary == len(resolved steps): the replayed tail is empty.
        response = client.post(
            f"/procedures/{pid}/reconduct", json={"re_establishment_boundary": 1}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] is True
    assert body["acquisition_halt"] is False


@pytest.mark.contract
def test_post_reconduct_halts_on_acquisition_in_replayed_tail() -> None:
    """Reconduct replaying a tail that starts with an acquisition halts for the
    operator (200, acquisition_halt=True), leaving the Procedure Running."""
    with TestClient(create_app()) as client:
        pid = _try_conduct_to_held(
            client,
            [
                {"kind": "setpoint", "address": "2bma:x", "value": 1.0},
                {"kind": "action", "name": "collect"},
            ],
        )
        # boundary == 1 skips the prefix setpoint; the tail starts with the action.
        response = client.post(
            f"/procedures/{pid}/reconduct", json={"re_establishment_boundary": 1}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] is False
    assert body["acquisition_halt"] is True


@pytest.mark.contract
def test_post_reconduct_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/procedures/{uuid4()}/reconduct", json={"re_establishment_boundary": 0}
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_reconduct_returns_409_for_defined_procedure() -> None:
    """A Defined (non-Held) Procedure cannot be reconducted."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        response = client.post(
            f"/procedures/{pid}/reconduct", json={"re_establishment_boundary": 0}
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_reconduct_returns_409_for_completed_procedure_with_resolved_steps() -> None:
    """A conduct pins resolved steps then completes; reconducting the (Completed)
    Procedure is refused by the resume status guard (not Held)."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        # Conduct an EMPTY step list: pins ResolvedStepsRecorded, then
        # start -> (no steps) -> complete, leaving the Procedure Completed
        # WITH a pinned (empty) resolved steps.
        conducted = client.post(f"/procedures/{pid}/conduct", json={"steps": []})
        assert conducted.status_code == 200
        assert conducted.json()["succeeded"] is True
        response = client.post(
            f"/procedures/{pid}/reconduct", json={"re_establishment_boundary": 0}
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_reconduct_returns_500_for_held_procedure_without_resolved_steps() -> None:
    """A Procedure started directly (no conduct) then held is Held WITHOUT a
    pinned resolved steps; reconduct cannot locate it (corruption-shaped 500)."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        assert client.post(f"/procedures/{pid}/start").status_code == 204
        assert client.post(f"/procedures/{pid}/hold", json={"reason": "pause"}).status_code == 204
        response = client.post(
            f"/procedures/{pid}/reconduct", json={"re_establishment_boundary": 0}
        )
    assert response.status_code == 500


@pytest.mark.contract
def test_post_reconduct_returns_422_for_negative_boundary() -> None:
    """Pydantic ge=0 rejects a negative boundary at the wire before the handler."""
    with TestClient(create_app()) as client:
        pid = _register(client)
        response = client.post(
            f"/procedures/{pid}/reconduct", json={"re_establishment_boundary": -1}
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_reconduct_returns_422_for_missing_boundary() -> None:
    with TestClient(create_app()) as client:
        pid = _register(client)
        response = client.post(f"/procedures/{pid}/reconduct", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_reconduct_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/procedures/not-a-uuid/reconduct", json={"re_establishment_boundary": 0}
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_reconduct_returns_400_for_boundary_past_step_count() -> None:
    """A boundary strictly past the pinned step count is rejected (it would
    replay an empty tail and silently auto-complete)."""
    with TestClient(create_app()) as client:
        pid = _try_conduct_to_held(
            client, [{"kind": "setpoint", "address": "2bma:x", "value": 1.0}]
        )
        response = client.post(
            f"/procedures/{pid}/reconduct", json={"re_establishment_boundary": 2}
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_reconduct_aborts_on_a_genuine_step_failure() -> None:
    """Replaying a tail whose setpoint still fails (unconnected address) aborts:
    200 with succeeded=False + acquisition_halt=False (a genuine step failure,
    not an acquisition halt)."""
    with TestClient(create_app()) as client:
        pid = _try_conduct_to_held(
            client, [{"kind": "setpoint", "address": "2bma:x", "value": 1.0}]
        )
        # boundary 0 re-drives the still-unconnected setpoint -> it fails again.
        response = client.post(
            f"/procedures/{pid}/reconduct", json={"re_establishment_boundary": 0}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] is False
    assert body["acquisition_halt"] is False
    assert body["failure"]["source_kind"] == "setpoint"
