"""Contract tests for `POST /procedures/{procedure_id}/reconduct`.

Resume-and-replay: resumes a Held Procedure and replays its pinned
step-list tail. 200 with replay outcomes in body; 404/409/422/500 for
protocol / guard / corruption faults.

Note on coverage: the 200 happy path (a clean replay that auto-completes)
requires a `Held` Procedure that carries a PINNED `ResolvedStepsRecorded`
resolved steps. The synchronous conduct flow today pins the resolved steps then runs
to a terminal state (Completed / Aborted) in one call, so there is no
API-reachable `Held + resolved-steps state yet (producing it -- a conduct that
pauses to Held instead of aborting on a halt, or a mid-conduct
cooperative hold -- is a follow-up slice). The clean / halt / step-failure
replay paths are covered end-to-end in
`tests/unit/operation/test_reconduct_procedure_handler.py` against a
seeded Held+resolved steps state. These contract tests cover the
API-reachable guard / fault surfaces.
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
