"""Contract tests for the `update_method_launch_spec` MCP tool.

Mirrors the REST endpoint. The method + parameters_schema are set up via
REST (the in-process app serves both surfaces); the launch_spec is then
set via the MCP tool.
"""

from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._mcp_helpers import open_session, parse_sse_data

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _method_with_schema(client: TestClient) -> UUID:
    cap_id = create_capability_via_api(client)
    method_id = UUID(
        client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "recon",
                "capability_id": cap_id,
                "needed_family_ids": [],
            },
        ).json()["method_id"]
    )
    schema: dict[str, Any] = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {"num_iter": {"type": "integer", "minimum": 1}},
    }
    client.post(f"/methods/{method_id}/parameters-schema", json={"parameters_schema": schema})
    return method_id


@pytest.mark.contract
def test_mcp_lists_update_method_launch_spec_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    tool_names = [t["name"] for t in parse_sse_data(response.text)["result"]["tools"]]
    assert "update_method_launch_spec" in tool_names


@pytest.mark.contract
def test_mcp_update_method_launch_spec_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        method_id = _method_with_schema(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "update_method_launch_spec",
                    "arguments": {
                        "method_id": str(method_id),
                        "launch_spec": {
                            "base_command": ["tomopy", "recon"],
                            "args": [{"name": "num_iter", "flag": "--num-iter", "required": True}],
                        },
                    },
                },
            },
            headers=headers,
        )
    assert parse_sse_data(response.text)["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_update_method_launch_spec_tool_is_error_for_unknown_parameter() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        method_id = _method_with_schema(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "update_method_launch_spec",
                    "arguments": {
                        "method_id": str(method_id),
                        "launch_spec": {
                            "base_command": ["x"],
                            "args": [{"name": "not_a_key", "flag": "--nope"}],
                        },
                    },
                },
            },
            headers=headers,
        )
    assert parse_sse_data(response.text)["result"]["isError"] is True
