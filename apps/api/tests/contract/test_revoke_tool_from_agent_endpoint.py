"""Contract tests for `POST /agents/{agent_id}/tools/revoke`."""

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
def test_post_revoke_returns_204_when_tool_was_granted() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(f"/agents/{agent_id}/tools/grant", json={"tool_name": "read_run"})
        response = client.post(
            f"/agents/{agent_id}/tools/revoke",
            json={
                "tool_name": "read_run",
                "reason": "tool no longer needed",
            },
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_revoke_idempotent_returns_204_when_tool_was_not_granted() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/tools/revoke",
            json={
                "tool_name": "never_granted",
                "reason": "tool no longer needed",
            },
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_revoke_404_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/agents/{uuid4()}/tools/revoke",
            json={"tool_name": "x", "reason": "tool no longer needed"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_revoke_409_on_deprecated_agent() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(f"/agents/{agent_id}/deprecate", json={"reason": "Superseded"})
        response = client.post(
            f"/agents/{agent_id}/tools/revoke",
            json={
                "tool_name": "x",
                "reason": "tool no longer needed",
            },
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_revoke_422_on_missing_tool_name() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(f"/agents/{agent_id}/tools/revoke", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revoke_422_on_over_cap_tool_name() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/tools/revoke",
            json={
                "tool_name": "x" * (AGENT_TOOL_NAME_MAX_LENGTH + 1),
                "reason": "tool no longer needed",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revoke_empty_reason_returns_422() -> None:
    """`min_length=1` rejects the empty string at the schema.

    Revoking a tool narrows what an autonomous Agent may do mid-campaign, so
    the reason is required for the same cause as `PolicyGrantRevoked`.
    """
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/tools/revoke",
            json={"tool_name": "read_run", "reason": ""},
        )
    assert response.status_code == 422
