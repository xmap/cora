"""Contract tests for the `inspect_plan_binding` MCP tool.

Same pinned shape as the REST endpoint; verifies tool listing
includes the new tool + that round-trip preview returns the
structured diagnostic + that unknown upstream surfaces as
isError.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _seed_practice_with_capability(
    client: TestClient, *, affordances: list[str], family_affordances: list[str]
) -> tuple[str, str]:
    """Seed full upstream chain. Returns (practice_id, asset_id)."""
    cap_id = create_capability_via_api(client, required_affordances=affordances)
    family_id = client.post(
        "/families",
        json={"name": "FlyMotion", "affordances": family_affordances},
    ).json()["family_id"]
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "Test Method",
            "capability_id": cap_id,
            "needed_family_ids": [family_id],
        },
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={
            "name": "Camera-04",
            "tier": "Unit",
            "parent_id": None,
            "facility_code": "cora",
        },
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": family_id})
    return practice_id, asset_id


@pytest.mark.contract
def test_mcp_lists_inspect_plan_binding_tool() -> None:
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
    assert "inspect_plan_binding" in tool_names


@pytest.mark.contract
def test_mcp_inspect_plan_binding_returns_structured_diagnostic() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id = _seed_practice_with_capability(
            client,
            affordances=["Rotatable", "Marking"],
            family_affordances=["Rotatable", "Marking"],
        )
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "inspect_plan_binding",
                    "arguments": {
                        "practice_id": practice_id,
                        "asset_ids": [asset_id],
                    },
                },
            },
            headers=session_headers,
        )

    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["practice_id"] == practice_id
    assert structured["binding_status"] == "Satisfied"
    assert structured["missing_family_ids"] == []
    assert structured["missing_affordances"] == []
    assert structured["capability_required_affordances"] == ["Marking", "Rotatable"]
    assert len(structured["wired_assets"]) == 1
    wired = structured["wired_assets"][0]
    assert wired["asset_id"] == asset_id
    assert wired["condition"] == "Nominal"
    assert wired["lifecycle"] == "Commissioned"
    assert wired["contributed_affordances"] == ["Marking", "Rotatable"]


@pytest.mark.contract
def test_mcp_inspect_plan_binding_returns_structured_diagnostic_on_failure_status() -> None:
    """A failure status (MissingAffordances) still returns a structured
    payload with the missing-set populated; pins MCP wire serialization
    of the failure branch."""
    with TestClient(create_app()) as client:
        practice_id, asset_id = _seed_practice_with_capability(
            client,
            affordances=["Rotatable", "Marking"],
            family_affordances=["Rotatable"],  # Marking missing
        )
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "inspect_plan_binding",
                    "arguments": {
                        "practice_id": practice_id,
                        "asset_ids": [asset_id],
                    },
                },
            },
            headers=session_headers,
        )

    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["binding_status"] == "MissingAffordances"
    assert structured["missing_affordances"] == ["Marking"]
    assert structured["missing_family_ids"] == []
    assert len(structured["wired_assets"]) == 1
    assert structured["wired_assets"][0]["contributed_affordances"] == ["Rotatable"]
    # In-memory MCP contract harness has no pool -> projection-backed
    # candidate enumeration skipped; field present but empty.
    assert structured["missing_affordance_candidates"] == []


@pytest.mark.contract
def test_mcp_inspect_plan_binding_returns_iserror_for_unknown_practice() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "inspect_plan_binding",
                    "arguments": {
                        "practice_id": str(uuid4()),
                        "asset_ids": [str(uuid4())],
                    },
                },
            },
            headers=session_headers,
        )

    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
