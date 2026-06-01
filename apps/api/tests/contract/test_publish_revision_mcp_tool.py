"""Contract tests for the `publish_revision` MCP tool."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.adapters.in_memory_permit_lookup import InMemoryPermitLookup
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_args() -> dict[str, Any]:
    return {
        "target_id": str(uuid4()),
        "quantity": "rotation_center",
        "operating_point": {"energy": 25.0, "optics_config": "5x"},
    }


def _revision_args(*, calibration_id: str) -> dict[str, Any]:
    return {
        "calibration_id": calibration_id,
        "value": {"center": 1024.5},
        "status": "Provisional",
        "source": {"kind": "Measured", "procedure_id": str(uuid4())},
    }


def _seed_calibration_and_revision(
    client: TestClient, session_headers: dict[str, str]
) -> tuple[str, str]:
    define_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "define_calibration", "arguments": _define_args()},
        },
        headers=session_headers,
    )
    assert define_response.status_code == 200, define_response.text
    define_body = parse_sse_data(define_response.text)
    cid = str(define_body["result"]["structuredContent"]["calibration_id"])

    revision_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "append_revision", "arguments": _revision_args(calibration_id=cid)},
        },
        headers=session_headers,
    )
    assert revision_response.status_code == 200, revision_response.text
    revision_body = parse_sse_data(revision_response.text)
    revision_id = str(revision_body["result"]["structuredContent"]["revision_id"])
    return cid, revision_id


def _seed_outbound_permit(app: FastAPI, peer_facility_id: str = "aps-2bm") -> UUID:
    permit_lookup = app.state.deps.permit_lookup
    assert isinstance(permit_lookup, InMemoryPermitLookup)
    permit_id = uuid4()
    permit_lookup.register_outbound(
        peer_facility_id=peer_facility_id,
        artifact_kind="CalibrationRevision",
        permit_id=permit_id,
    )
    return permit_id


@pytest.mark.contract
def test_mcp_lists_publish_revision_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "publish_revision" in tool_names


@pytest.mark.contract
def test_mcp_publish_revision_tool_returns_receipt_id_on_happy_path() -> None:
    app = create_app()
    with TestClient(app) as client:
        session_headers = open_session(client)
        cid, revision_id = _seed_calibration_and_revision(client, session_headers)
        _seed_outbound_permit(app)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "publish_revision",
                    "arguments": {
                        "calibration_id": cid,
                        "revision_id": revision_id,
                        "peer_facility_id": "aps-2bm",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200, response.text
    body = parse_sse_data(response.text)
    receipt_id = body["result"]["structuredContent"]["receipt_id"]
    UUID(receipt_id)


@pytest.mark.contract
def test_mcp_publish_revision_tool_carries_publish_revision_in_output_schema() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool: dict[str, Any] = next(
        t for t in body["result"]["tools"] if t["name"] == "publish_revision"
    )
    output_schema: dict[str, Any] = tool.get("outputSchema") or {}
    assert "properties" in output_schema
    properties: dict[str, Any] = output_schema["properties"]
    assert "receipt_id" in properties
