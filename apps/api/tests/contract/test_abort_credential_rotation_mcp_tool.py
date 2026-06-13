"""Contract tests for the `abort_credential_rotation` MCP tool.

The happy-path Rotating -> Active transition cannot be exercised end-
to-end through the MCP surface in this slice because the upstream
`register_credential` + `start_credential_rotation` slice tools are
landed as sibling Credential rotation slices. These tests pin
tool listing, structured-content shape on the happy path (via REST
dependency override), and the `isError: true` mapping for the
decider-layer FSM rejection plus the unknown-credential branch.
"""

from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.credential import (
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialStatus,
)
from cora.federation.features.abort_credential_rotation.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH
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
    state = cast("object", app.state.federation)  # type: ignore[attr-defined]
    object.__setattr__(state, "abort_credential_rotation", handler)


@pytest.mark.contract
def test_mcp_lists_abort_credential_rotation_tool() -> None:
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
    assert "abort_credential_rotation" in tool_names


@pytest.mark.contract
def test_mcp_abort_credential_rotation_tool_returns_structured_credential_id() -> None:
    """Happy path via handler override: tool returns structured credential_id
    (matches REST 204 + path-id contract)."""
    app = create_app()
    credential_id = uuid4()

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
            name="abort_credential_rotation",
            arguments={
                "credential_id": str(credential_id),
                "reason": "peer refused new material",
            },
        )
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["credential_id"] == str(credential_id)
    UUID(result["structuredContent"]["credential_id"])


@pytest.mark.contract
def test_mcp_abort_credential_rotation_tool_accepts_omitted_reason() -> None:
    """`reason` is optional; omitting it from arguments succeeds."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=21,
            name="abort_credential_rotation",
            arguments={"credential_id": str(uuid4())},
        )
    assert body["result"]["isError"] is False, body


@pytest.mark.contract
def test_mcp_abort_credential_rotation_tool_returns_iserror_on_active_credential() -> None:
    """Decider-layer FSM rejection (Active != Rotating) surfaces through
    FastMCP as isError: true."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialCannotRotateError(
            UUID(int=1),
            CredentialStatus.ACTIVE,
            "abort_rotation",
        )

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=30,
            name="abort_credential_rotation",
            arguments={"credential_id": str(uuid4()), "reason": "x"},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_abort_credential_rotation_tool_returns_iserror_on_unknown_credential() -> None:
    """A handler raising CredentialNotFoundError surfaces through FastMCP."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialNotFoundError(UUID(int=0))

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=40,
            name="abort_credential_rotation",
            arguments={"credential_id": str(uuid4()), "reason": "x"},
        )
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_abort_credential_rotation_tool_rejects_missing_required_argument() -> None:
    """Pydantic-layer rejection (missing credential_id) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=60,
            name="abort_credential_rotation",
            arguments={"reason": "x"},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_abort_credential_rotation_tool_rejects_overlong_reason() -> None:
    """Pydantic max_length=500 enforcement bubbles as isError via FastMCP."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=70,
            name="abort_credential_rotation",
            arguments={
                "credential_id": str(uuid4()),
                "reason": "x" * (REASON_MAX_LENGTH + 1),
            },
        )
    assert body["result"]["isError"] is True
