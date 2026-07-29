"""Contract tests for the `ingest_scan` REST route and MCP tool.

The test app configures no `posix_checksum_roots`, so every locator is
refused before any domain machinery runs; these tests pin the surface
contract (the tool is listed, the route exists in OpenAPI, refusals
carry the remedy at the right status), while the full file-to-record
happy path lives in the integration tier against real Postgres and a
real file.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

pytestmark = pytest.mark.contract


def _body() -> dict[str, object]:
    return {
        "locator": "file:///data2/2026-07/doe-12345/scan_001.h5",
        "producing_asset_id": str(uuid4()),
        "supply_id": str(uuid4()),
        "access_protocol": "POSIX",
    }


def test_openapi_lists_the_ingest_route() -> None:
    with TestClient(create_app()) as client:
        paths = client.get("/openapi.json").json()["paths"]
        assert "/scans/ingest" in paths
        assert "post" in paths["/scans/ingest"]


def test_post_scans_ingest_unreachable_locator_returns_400_with_remedy() -> None:
    """No roots configured: the reader refuses the locator, and the 400
    detail carries the reason rather than a bare rejection."""
    with TestClient(create_app()) as client:
        response = client.post("/scans/ingest", json=_body())
        assert response.status_code == 400
        assert "not readable" in response.json()["detail"]


def test_post_scans_ingest_naive_captured_at_returns_422() -> None:
    """The body model requires timezone-aware captured_at; a naive
    datetime never reaches the handler."""
    with TestClient(create_app()) as client:
        body = _body() | {"captured_at": "2026-07-29T10:15:30"}
        response = client.post("/scans/ingest", json=body)
        assert response.status_code == 422


def test_mcp_lists_ingest_scan_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        tools = parse_sse_data(response.text)["result"]["tools"]
        assert "ingest_scan" in {tool["name"] for tool in tools}


def test_mcp_ingest_scan_tool_surfaces_the_refusal() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "ingest_scan", "arguments": _body()},
            },
        )
        result = parse_sse_data(response.text)["result"]
        assert result["isError"] is True
        assert "not readable" in result["content"][0]["text"]
