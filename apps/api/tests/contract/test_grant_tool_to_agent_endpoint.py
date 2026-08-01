"""Contract tests for `POST /agents/{agent_id}/tools/grant`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.agent.aggregates.agent import AGENT_TOOL_NAME_MAX_LENGTH
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
def test_post_grant_returns_204_on_defined_agent() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/tools/grant",
            json={"tool_name": "read_run"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_grant_idempotent_re_grant_returns_204() -> None:
    """Re-grant of an existing tool succeeds silently with 204."""
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        first = client.post(f"/agents/{agent_id}/tools/grant", json={"tool_name": "read_run"})
        second = client.post(f"/agents/{agent_id}/tools/grant", json={"tool_name": "read_run"})
    assert first.status_code == 204
    assert second.status_code == 204


@pytest.mark.contract
def test_post_grant_404_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/agents/{uuid4()}/tools/grant", json={"tool_name": "read_run"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_grant_409_on_deprecated_agent() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(f"/agents/{agent_id}/deprecate", json={"reason": "Superseded"})
        response = client.post(f"/agents/{agent_id}/tools/grant", json={"tool_name": "read_run"})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_grant_422_on_over_cap_tool_name() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/tools/grant",
            json={"tool_name": "x" * (AGENT_TOOL_NAME_MAX_LENGTH + 1)},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_grant_422_on_missing_tool_name() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(f"/agents/{agent_id}/tools/grant", json={})
    assert response.status_code == 422
