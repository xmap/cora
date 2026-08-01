"""Contract tests for the `withdraw_clearance_template` MCP tool.

Pins tool registration on the MCP server, the input-schema `template_id`
requirement, the structured output shape (`WithdrawClearanceTemplateOutput`
carrying `template_id` round-tripped), the handler-layer rejection path
(bubbled via FastMCP as `isError: true`, the same idiom REST surfaces
as 409), and Authorize-Deny bubbling as `isError: true` (mirrors how
the production `TrustAuthorize` would on a Deny).
"""

from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.errors import UnauthorizedError
from tests.contract._mcp_helpers import open_session, parse_sse_data

_FACILITY_CODE = "cora"


def _define_template_via_tool(
    client: TestClient,
    session_headers: dict[str, str],
    *,
    code: str = "radiation-safety-form",
    title: str = "Radiation Safety Form",
    facility_code: str = _FACILITY_CODE,
) -> UUID:
    """Seed a Draft ClearanceTemplate via the sibling
    `define_clearance_template` MCP tool. Same in-process in-memory
    store backs every tool via the lifespan-built Kernel."""
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "define_clearance_template",
                "arguments": {
                    "code": code,
                    "title": title,
                    "facility_code": facility_code,
                },
            },
        },
        headers=session_headers,
    )
    assert response.status_code == 200, response.text
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False, body
    return UUID(body["result"]["structuredContent"]["template_id"])


def _withdraw_template_via_tool(
    client: TestClient,
    session_headers: dict[str, str],
    template_id: UUID,
    *,
    rpc_id: int = 101,
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "tools/call",
            "params": {
                "name": "withdraw_clearance_template",
                "arguments": {"template_id": str(template_id), "reason": "policy change"},
            },
        },
        headers=session_headers,
    )
    assert response.status_code == 200, response.text
    return parse_sse_data(response.text)


@pytest.mark.contract
def test_mcp_lists_withdraw_clearance_template_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "withdraw_clearance_template" in tool_names


@pytest.mark.contract
def test_mcp_withdraw_clearance_template_input_schema_requires_template_id() -> None:
    """The lone argument `template_id` must be advertised as required."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tools = {t["name"]: t for t in body["result"]["tools"]}
    schema = tools["withdraw_clearance_template"]["inputSchema"]
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    assert "template_id" in properties
    assert "template_id" in required


@pytest.mark.contract
def test_mcp_withdraw_clearance_template_tool_returns_structured_template_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        template_id = _define_template_via_tool(client, session_headers)
        body = _withdraw_template_via_tool(client, session_headers, template_id)
    result = body["result"]
    assert result["isError"] is False, result
    structured = result["structuredContent"]
    assert structured["template_id"] == str(template_id)


@pytest.mark.contract
def test_mcp_withdraw_clearance_template_tool_returns_iserror_when_already_withdrawn() -> None:
    """Withdrawing a template that is already Withdrawn raises in the
    decider (Withdrawn is terminal); FastMCP wraps as `isError: true`
    (matches REST 409 semantically)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        template_id = _define_template_via_tool(client, session_headers)
        first = _withdraw_template_via_tool(client, session_headers, template_id, rpc_id=200)
        assert first["result"]["isError"] is False, first
        second = _withdraw_template_via_tool(client, session_headers, template_id, rpc_id=201)
    assert second["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_withdraw_clearance_template_tool_returns_iserror_on_unknown_template() -> None:
    """Withdrawing an unknown template_id loads an empty stream; the
    decider rejects it as not in a withdraw-eligible status; FastMCP
    wraps as `isError: true`."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        body = _withdraw_template_via_tool(client, session_headers, uuid4(), rpc_id=300)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_withdraw_clearance_template_tool_authorize_deny_bubbles_as_iserror() -> None:
    """Replace the wired handler with one that raises `UnauthorizedError`,
    mirroring how the production `TrustAuthorize` would on a Deny. The MCP
    tool surfaces it as `isError: true` per the FastMCP contract."""

    async def _denying_handler(*_args: object, **_kwargs: object) -> None:
        raise UnauthorizedError("denied for test")

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            withdraw_clearance_template=_denying_handler,
        )
        session_headers = open_session(client)
        body = _withdraw_template_via_tool(client, session_headers, uuid4(), rpc_id=400)

    assert body["result"]["isError"] is True
