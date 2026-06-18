"""Contract tests for the `get_method` MCP tool.

Mirrors `test_get_family_mcp_tool.py`. Pinned structured output
shape: `{id, name, needed_family_ids, status}`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_method_via_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "XRF Mapping",
    needed_family_ids: list[str] | None = None,
) -> UUID:

    cap_id = create_capability_via_api(client)
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_method",
                "arguments": {
                    "execution_pattern": "Batch",
                    "name": name,
                    "capability_id": cap_id,
                    "needed_family_ids": (
                        needed_family_ids if needed_family_ids is not None else []
                    ),
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["method_id"])


@pytest.mark.contract
def test_mcp_lists_get_method_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_method" in tool_names


@pytest.mark.contract
def test_mcp_get_method_tool_returns_structured_method_for_known_id() -> None:
    cap1 = str(uuid4())
    with TestClient(create_app()) as client:
        headers = open_session(client)
        method_id = _define_method_via_tool(
            client, headers, name="XRF Mapping", needed_family_ids=[cap1]
        )
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_method",
                    "arguments": {"method_id": str(method_id)},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["id"] == str(method_id)
    assert structured["name"] == "XRF Mapping"
    assert structured["status"] == "Defined"
    assert structured["needed_family_ids"] == [cap1]
    # Null until version_method runs (6b).
    assert structured["version"] is None
    # compute classification mirrors the REST MethodResponse.
    assert structured["execution_pattern"] == "Batch"
    assert structured["monotone_quality"] is False
    assert structured["resumable_from_checkpoint"] is False


@pytest.mark.contract
def test_mcp_get_method_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_method",
                    "arguments": {"method_id": str(uuid4())},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
