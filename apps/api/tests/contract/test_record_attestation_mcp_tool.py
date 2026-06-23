"""Contract tests for the ``record_attestation`` MCP tool.

## Scope

The TestClient app does not pre-seed any Distribution. The tool is slim
(``dataset_id`` + ``distribution_id`` + ``kind``); CORA computes the
checksum itself. We pin:

  - Tool is listed by ``tools/list``.
  - ``tools/call`` rejects an unknown kind at the MCP arg schema.
  - ``tools/call`` returns isError=True with a 404-style message when the
    dataset_id never resolves.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _record_args(
    *,
    dataset_id: str | None = None,
    distribution_id: str | None = None,
    **overrides: object,
) -> dict[str, object]:
    base: dict[str, object] = {
        "dataset_id": dataset_id or str(uuid4()),
        "distribution_id": distribution_id or str(uuid4()),
        "kind": "ChecksumVerified",
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_record_attestation_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "record_attestation" in tool_names


@pytest.mark.contract
def test_mcp_record_attestation_returns_iserror_for_unknown_dataset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "record_attestation",
                    "arguments": _record_args(),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_record_attestation_rejects_unknown_kind() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "record_attestation",
                    "arguments": _record_args(kind="HashChecked"),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
