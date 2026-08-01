"""Contract tests for `POST /agents/{agent_id}/target-plan`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_body() -> dict[str, object]:
    return {
        "kind": "RunInitiator",
        "name": "Run Initiator",
        "version": "v1",
        "model_ref": {
            "provider": "deterministic",
            "model": "agent:RunInitiator:v1",
            "snapshot_pin": None,
        },
    }


@pytest.mark.contract
def test_post_update_target_plan_returns_204() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/target-plan",
            json={"target_plan_id": str(uuid4())},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_update_target_plan_clears_with_null() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(
            f"/agents/{agent_id}/target-plan",
            json={"target_plan_id": str(uuid4())},
        )
        response = client.post(f"/agents/{agent_id}/target-plan", json={"target_plan_id": None})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_update_target_plan_clears_with_empty_body() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(f"/agents/{agent_id}/target-plan", json={})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_update_target_plan_404_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/agents/{uuid4()}/target-plan", json={"target_plan_id": str(uuid4())}
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_update_target_plan_409_on_deprecated_agent() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(f"/agents/{agent_id}/deprecate", json={"reason": "Superseded"})
        response = client.post(
            f"/agents/{agent_id}/target-plan", json={"target_plan_id": str(uuid4())}
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_update_target_plan_422_on_malformed_uuid() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/target-plan", json={"target_plan_id": "not-a-uuid"}
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_update_target_plan_idempotent_returns_204_on_same_plan() -> None:
    plan_id = str(uuid4())
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        first = client.post(f"/agents/{agent_id}/target-plan", json={"target_plan_id": plan_id})
        second = client.post(f"/agents/{agent_id}/target-plan", json={"target_plan_id": plan_id})
    assert first.status_code == 204
    assert second.status_code == 204
