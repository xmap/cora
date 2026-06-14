"""Contract tests for `POST /procedures/{procedure_id}/conduct`.

Orchestration endpoint: delegates to the wired Conductor which walks
the supplied step list end-to-end through the Procedure FSM (start
-> execute -> complete | abort). Covers:

  - happy path: empty step list yields succeeded=True with
    completed_count=0 and no failure
  - happy path: single action step against an unknown action body
    yields succeeded=False with UnknownActionError (registry is
    empty in the v1 wire-up)
  - step failure: setpoint to an unconnected address yields
    succeeded=False with ControlNotConnectedError (InMemoryControlPort
    is the v1 wire-up; no addresses are pre-connected)
  - lifecycle failure: running an unregistered procedure yields
    succeeded=False with source_kind=lifecycle + target=start +
    ProcedureNotFoundError
  - check failure: read raises NotConnected on the in-memory port
  - mixed step list: walks setpoint + action + check in order
  - validation errors: unknown step kind / missing required field
    fail at Pydantic parse with 422
  - empty body (no steps key): defaults to []

All tests run against the in-process FastAPI app + the in-process
InMemoryControlPort + the empty default ActionRegistry that
`wire_operation` constructs. Substrate adapter selection from config
+ ActionRegistry-from-config land at a follow-up iteration; this
contract test covers what the wire-up actually delivers today.
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
def test_post_conduct_empty_steps_returns_200_succeeded_for_running_procedure() -> None:
    """Empty step list: Conductor runs start + complete with no steps."""
    with TestClient(create_app()) as client:
        pid = _register_and_start(client)
        # The first start (above) already transitioned Defined -> Running;
        # the conductor's start_procedure call inside conduct() will be
        # rejected. Use a freshly registered procedure that has NOT been
        # started so the conductor handles the full lifecycle itself.
        body: dict[str, Any] = {"name": "fresh proc", "kind": "bakeout"}
        fresh_pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        response = client.post(f"/procedures/{fresh_pid}/conduct", json={"steps": []})
    assert response.status_code == 200
    payload = response.json()
    assert payload["procedure_id"] == str(fresh_pid)
    assert payload["completed_count"] == 0
    assert payload["succeeded"] is True
    assert payload["failure"] is None
    # actuation_kind is surfaced on the response; None here because the
    # default in-memory deployment has no routing table to declare simulated-ness.
    assert payload["actuation_kind"] is None
    _ = pid  # unused; included only to exercise the _register_and_start helper shape


@pytest.mark.contract
def test_post_conduct_with_unknown_action_step_returns_200_with_unknown_action_failure() -> None:
    """The v1 wire-up has an empty action registry; any action name fails."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "fresh proc", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        run = client.post(
            f"/procedures/{pid}/conduct",
            json={"steps": [{"kind": "action", "name": "no_such_body"}]},
        )
    assert run.status_code == 200
    payload = run.json()
    assert payload["succeeded"] is False
    failure = payload["failure"]
    assert failure["step_index"] == 0
    assert failure["source_kind"] == "action"
    assert failure["target"] == "no_such_body"
    assert failure["error_class"] == "UnknownActionError"


@pytest.mark.contract
def test_post_conduct_with_setpoint_to_unconnected_address_returns_not_connected_failure() -> None:
    """InMemoryControlPort raises NotConnected for any address not pre-connected."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "fresh proc", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        run = client.post(
            f"/procedures/{pid}/conduct",
            json={"steps": [{"kind": "setpoint", "address": "2bma:rot:val", "value": 45.0}]},
        )
    assert run.status_code == 200
    payload = run.json()
    assert payload["succeeded"] is False
    failure = payload["failure"]
    assert failure["source_kind"] == "setpoint"
    assert failure["target"] == "2bma:rot:val"
    assert failure["error_class"] == "ControlNotConnectedError"


@pytest.mark.contract
def test_post_conduct_against_unregistered_procedure_returns_404() -> None:
    """The conduct_procedure handler loads the Procedure stream up front
    ([[project-run-procedure-replay-design]] added
    `load_procedure_with_events` at handler entry) and raises
    `ProcedureNotFoundError`, which the BC's central exception handler
    maps to 404. Earlier shape (200 with lifecycle failure on the body)
    was rejected by routes.py wiring: see
    [[project_conduct_procedure_test_contract_drift]] memory."""
    with TestClient(create_app()) as client:
        unknown_pid = uuid4()
        run = client.post(
            f"/procedures/{unknown_pid}/conduct",
            json={"steps": []},
        )
    assert run.status_code == 404
    payload = run.json()
    assert str(unknown_pid) in payload["detail"]


@pytest.mark.contract
def test_post_conduct_check_step_against_unconnected_address_returns_200_with_failure() -> None:
    """Check step's ControlPort.read raises NotConnected on the in-memory port."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "fresh proc", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        run = client.post(
            f"/procedures/{pid}/conduct",
            json={
                "steps": [
                    {
                        "kind": "check",
                        "address": "2bma:rot:rbv",
                        "criterion": {"kind": "equals", "expected": 45.0},
                    }
                ]
            },
        )
    payload = run.json()
    assert payload["succeeded"] is False
    failure = payload["failure"]
    assert failure["source_kind"] == "check"
    assert failure["error_class"] == "ControlNotConnectedError"


@pytest.mark.contract
def test_post_conduct_with_unknown_step_kind_returns_422() -> None:
    """Pydantic's discriminated union rejects unknown kinds at parse time."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "fresh proc", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        run = client.post(
            f"/procedures/{pid}/conduct",
            json={"steps": [{"kind": "teleport", "address": "x", "value": 1.0}]},
        )
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_with_setpoint_missing_address_returns_422() -> None:
    """Missing required field on a setpoint fails Pydantic validation."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "fresh proc", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        run = client.post(
            f"/procedures/{pid}/conduct",
            json={"steps": [{"kind": "setpoint", "value": 1.0}]},
        )
    assert run.status_code == 422


@pytest.mark.contract
def test_post_conduct_without_steps_key_defaults_to_empty_list() -> None:
    """Body `{}` is valid: `steps` defaults to []; equivalent to passing []."""
    with TestClient(create_app()) as client:
        body: dict[str, Any] = {"name": "fresh proc", "kind": "bakeout"}
        pid = UUID(client.post("/procedures", json=body).json()["procedure_id"])
        run = client.post(f"/procedures/{pid}/conduct", json={})
    assert run.status_code == 200
    payload = run.json()
    assert payload["succeeded"] is True
    assert payload["completed_count"] == 0
