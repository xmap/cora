"""Contract tests for the `revoke_grant` MCP tool.

Mirrors the REST endpoint contract through the MCP surface: pins tool
listing, structured-content shape on the happy path (via handler
override), and the `isError: true` mapping for the unknown-policy branch
plus Pydantic-layer argument rejections.

The happy-path fold is exercised end-to-end by the handler test and the
Postgres integration test; this file only exercises the tool wire
(FastMCP shape, status mapping).
"""

from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.trust.aggregates.policy import PolicyNotFoundError
from cora.trust.features.revoke_grant.handler import Handler
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _call_tool(
    client: TestClient,
    *,
    headers: dict[str, str],
    request_id: int,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return parse_sse_data(response.text)


def _override_handler(app: object, handler: Handler) -> None:
    """Override the MCP-bound handler bundle so the tool returns the fake."""
    state = cast("object", app.state.trust)  # type: ignore[attr-defined]
    object.__setattr__(state, "revoke_grant", handler)


def _args() -> dict[str, str]:
    return {
        "policy_id": str(uuid4()),
        "principal_id": str(uuid4()),
        "reason": "agent decommissioned",
    }


@pytest.mark.contract
def test_mcp_lists_revoke_grant_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "revoke_grant" in tool_names


@pytest.mark.contract
def test_mcp_revoke_grant_tool_returns_structured_ids() -> None:
    """Happy path via handler override: tool returns structured policy_id +
    principal_id (matches REST 204 + path-id contract)."""
    app = create_app()
    policy_id = uuid4()
    principal_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=20,
            name="revoke_grant",
            arguments={
                "policy_id": str(policy_id),
                "principal_id": str(principal_id),
                "reason": "agent decommissioned",
            },
        )
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["policy_id"] == str(policy_id)
    assert result["structuredContent"]["principal_id"] == str(principal_id)


@pytest.mark.contract
def test_mcp_revoke_grant_tool_returns_iserror_on_unknown_policy() -> None:
    """A handler raising PolicyNotFoundError surfaces through FastMCP."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise PolicyNotFoundError(UUID(int=0))

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=40,
            name="revoke_grant",
            arguments=_args(),
        )
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_revoke_grant_tool_rejects_missing_required_argument() -> None:
    """Pydantic-layer rejection (missing reason) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=60,
            name="revoke_grant",
            arguments={"policy_id": str(uuid4()), "principal_id": str(uuid4())},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_revoke_grant_tool_rejects_malformed_policy_id() -> None:
    """Pydantic-layer rejection (non-UUID policy_id) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=70,
            name="revoke_grant",
            arguments={
                "policy_id": "not-a-uuid",
                "principal_id": str(uuid4()),
                "reason": "x",
            },
        )
    assert body["result"]["isError"] is True
