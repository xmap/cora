"""Contract tests for the `conduct_until_converged` MCP tool.

Mirrors the REST contract test (same wire shape + same in-process wire-up).
Covers tool listing, a loud-fail-in-structured-content outcome (a recipe-LESS
Procedure conducted with an empty pass deposits no convergence value), and the
not-found wrap.

Compute-driven convergence is driven over MCP (as over REST) via the RECIPE
path: register-from-recipe with a RecipeComputeStep, then conduct-until-converged
with steps:[]. The literal MCP step array (like REST) intentionally excludes
capture / compute steps (validation-only); the recipe is the channel for them.
The recipe-path coverage lives in the REST contract test (one in-process app
exercises both surfaces through the same handler); a converging end-to-end loop
is exercised by the in-memory scenario.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_CRITERION: dict[str, Any] = {"kind": "within_tolerance", "expected": 0.0, "tolerance": 0.5}


def _register_via_mcp(client: TestClient, headers: dict[str, str], *, request_id: int) -> UUID:
    reg = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": "register_procedure",
                "arguments": {"name": "auto align", "kind": "rotation_alignment"},
            },
        },
        headers=headers,
    )
    return UUID(parse_sse_data(reg.text)["result"]["structuredContent"]["procedure_id"])


@pytest.mark.contract
def test_mcp_lists_conduct_until_converged_tool() -> None:
    """The Operation BC registers the conduct_until_converged tool on the FastMCP server."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "conduct_until_converged" in tool_names


@pytest.mark.contract
def test_mcp_conduct_until_converged_empty_pass_loud_fails_in_structured_content() -> None:
    """An empty pass succeeds but deposits no convergence value -> failure in result."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        pid = _register_via_mcp(client, headers, request_id=1)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "conduct_until_converged",
                    "arguments": {
                        "procedure_id": str(pid),
                        "body": {
                            "convergence_capture_name": "offset",
                            "criterion": _CRITERION,
                            "steps": [],
                            "max_consecutive_unconverged_iterations": 3,
                        },
                    },
                },
            },
            headers=headers,
        )
    structured: dict[str, Any] = parse_sse_data(response.text)["result"]["structuredContent"]
    assert structured["procedure_id"] == str(pid)
    assert structured["succeeded"] is False
    assert structured["failure"]["error_class"] == "ComputeMeasurementNotFound"


@pytest.mark.contract
def test_mcp_conduct_until_converged_against_unregistered_procedure_returns_iserror() -> None:
    """The handler loads the Procedure stream up front -> ProcedureNotFoundError wrap."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        unknown_pid = uuid4()
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "conduct_until_converged",
                    "arguments": {
                        "procedure_id": str(unknown_pid),
                        "body": {
                            "convergence_capture_name": "offset",
                            "criterion": _CRITERION,
                            "steps": [],
                        },
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert str(unknown_pid) in body["result"]["content"][0]["text"]
