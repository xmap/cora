"""Contract tests for the `append_observations` MCP tool.

Mirrors `test_append_inferences_mcp_tool.py` shape: tool listed,
single-entry happy path, missing-aggregate error path. Single-entry
shape per the MCP convention (agents typically reason about one
observation at a time; the HTTP route handles batching).
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._mcp_helpers import open_session, parse_sse_data
from tests.contract._subject_helpers import register_active_asset


def _setup_full_run(client: TestClient) -> str:
    _cap_id = create_capability_via_api(client)
    """Seed full upstream chain + start a Run. Returns the run_id.
    Mirrors the helper in test_append_observations_endpoint.py."""
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "M",
            "capability_id": _cap_id,
            "needed_family_ids": [cap_id],
        },
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "A", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "test"}
    )
    run_id = client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]
    return run_id


def _good_args(run_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_id": run_id,
        "channel_name": "T_sample",
        "value": 295.1,
        "sampled_at": "2026-05-14T12:00:00+00:00",
        "sampling_procedure": "baseline",
        "units": "K",
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_append_run_readings_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "append_observations" in tool_names


@pytest.mark.contract
def test_mcp_append_run_readings_tool_succeeds_on_minimum_args() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "append_observations",
                    "arguments": _good_args(run_id),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    # Tool returns int (entry count); MCP wraps as structured content.
    assert body["result"]["structuredContent"]["result"] == 1


@pytest.mark.contract
def test_mcp_append_run_readings_tool_returns_iserror_for_unknown_run() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "append_observations",
                    "arguments": _good_args(str(uuid4())),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
