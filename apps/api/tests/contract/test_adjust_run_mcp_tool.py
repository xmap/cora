"""Contract tests for the `adjust_run` MCP tool."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._mcp_helpers import open_session, parse_sse_data
from tests.contract._subject_helpers import register_active_asset

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _energy_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            }
        },
    }


def _setup_full_run(client: TestClient) -> str:
    _cap_id = create_capability_via_api(client)
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods", json={"name": "M", "capability_id": _cap_id, "needed_family_ids": [cap_id]}
    ).json()["method_id"]
    r = client.post(
        f"/methods/{method_id}/parameters-schema",
        json={"parameters_schema": _energy_schema()},
    )
    assert r.status_code == 204
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
    client.patch(
        f"/plans/{plan_id}/default-parameters",
        json={"default_parameters_patch": {"energy": 10.0}},
    )
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": mount_asset_id, "reason": "test"},
    )
    run_id = client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]
    return run_id


@pytest.mark.contract
def test_mcp_lists_adjust_run_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "adjust_run" in tool_names


@pytest.mark.contract
def test_mcp_adjust_run_tool_succeeds_on_happy_path() -> None:
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
                    "name": "adjust_run",
                    "arguments": {
                        "run_id": run_id,
                        "parameters_patch": {"energy": 12.0},
                        "reason": "re-center",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_adjust_run_tool_passes_decision_id_through() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "adjust_run",
                    "arguments": {
                        "run_id": run_id,
                        "parameters_patch": {"energy": 13.0},
                        "reason": "agent steering",
                        "decided_by_decision_id": str(uuid4()),
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_adjust_run_tool_surfaces_run_not_found_error() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "adjust_run",
                    "arguments": {
                        "run_id": str(uuid4()),
                        "parameters_patch": {"x": 1},
                        "reason": "x",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_adjust_run_tool_surfaces_whitespace_reason_error() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "adjust_run",
                    "arguments": {
                        "run_id": run_id,
                        "parameters_patch": {"energy": 12.0},
                        "reason": "   ",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
