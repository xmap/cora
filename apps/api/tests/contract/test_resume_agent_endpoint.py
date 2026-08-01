"""Contract tests for `POST /agents/{agent_id}/resume`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_body() -> dict[str, object]:
    return {
        "kind": "RunDebriefer",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
    }


@pytest.mark.contract
def test_post_resume_returns_204_on_suspended_agent() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(f"/agents/{agent_id}/version")
        client.post(f"/agents/{agent_id}/suspend", json={"reason": "x"})
        response = client.post(f"/agents/{agent_id}/resume")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_resume_409_on_versioned_agent() -> None:
    """Resume is only valid from Suspended."""
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(f"/agents/{agent_id}/version")
        response = client.post(f"/agents/{agent_id}/resume")
    assert response.status_code == 409


@pytest.mark.contract
def test_post_resume_404_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/agents/{uuid4()}/resume")
    assert response.status_code == 404


@pytest.mark.contract
def test_suspend_then_resume_then_suspend_cycle_succeeds() -> None:
    """Verify the non-terminal cycle: Versioned <-> Suspended."""
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(f"/agents/{agent_id}/version")
        first_suspend = client.post(f"/agents/{agent_id}/suspend", json={"reason": "first"})
        first_resume = client.post(f"/agents/{agent_id}/resume")
        second_suspend = client.post(f"/agents/{agent_id}/suspend", json={"reason": "second"})
    assert first_suspend.status_code == 204
    assert first_resume.status_code == 204
    assert second_suspend.status_code == 204
