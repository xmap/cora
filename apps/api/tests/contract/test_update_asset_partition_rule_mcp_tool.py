"""Contract tests for the `update_asset_partition_rule` MCP tool.

Full bootstrap is done via other MCP tools (define_family,
register_asset, add_asset_family) so the entire write path is
exercised over JSON-RPC, not Python imports. The Asset must carry a
Family whose name is "PseudoAxis" before the rule can be set.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _call_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    call_id: int,
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=headers,
    )
    return parse_sse_data(response.text)


def _setup_pseudoaxis_asset(client: TestClient, headers: dict[str, str]) -> UUID:
    """Define the PseudoAxis Family + register Asset + assign Family. Returns asset_id."""
    fam_body = _call_tool(
        client,
        headers,
        call_id=10,
        name="define_family",
        arguments={"name": "PseudoAxis", "affordances": []},
    )
    fam_id = UUID(fam_body["result"]["structuredContent"]["family_id"])  # type: ignore[index]

    asset_body = _call_tool(
        client,
        headers,
        call_id=11,
        name="register_asset",
        arguments={"name": "ANL", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    )
    asset_id = UUID(asset_body["result"]["structuredContent"]["asset_id"])  # type: ignore[index]

    add_body = _call_tool(
        client,
        headers,
        call_id=12,
        name="add_asset_family",
        arguments={"asset_id": str(asset_id), "family_id": str(fam_id)},
    )
    assert add_body["result"]["isError"] is False  # type: ignore[index]

    return asset_id


@pytest.mark.contract
def test_mcp_lists_update_asset_partition_rule_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "update_asset_partition_rule" in tool_names


@pytest.mark.contract
def test_mcp_update_asset_partition_rule_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _setup_pseudoaxis_asset(client, headers)
        body = _call_tool(
            client,
            headers,
            call_id=20,
            name="update_asset_partition_rule",
            arguments={
                "asset_id": str(asset_id),
                "partition_rule": {
                    "kind": "Affine",
                    "gain": 2.0,
                    "offset": 0.5,
                    "unit_in": "mm",
                    "unit_out": "deg",
                },
            },
        )
    assert body["result"]["isError"] is False  # type: ignore[index]


@pytest.mark.contract
def test_mcp_update_asset_partition_rule_tool_succeeds_when_clearing_rule() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _setup_pseudoaxis_asset(client, headers)
        set_body = _call_tool(
            client,
            headers,
            call_id=20,
            name="update_asset_partition_rule",
            arguments={
                "asset_id": str(asset_id),
                "partition_rule": {"kind": "Affine", "gain": 1.0, "offset": 0.0},
            },
        )
        assert set_body["result"]["isError"] is False  # type: ignore[index]
        clear_body = _call_tool(
            client,
            headers,
            call_id=21,
            name="update_asset_partition_rule",
            arguments={"asset_id": str(asset_id), "partition_rule": None},
        )
    assert clear_body["result"]["isError"] is False  # type: ignore[index]


@pytest.mark.contract
def test_mcp_update_asset_partition_rule_tool_returns_iserror_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers,
            call_id=21,
            name="update_asset_partition_rule",
            arguments={
                "asset_id": str(uuid4()),
                "partition_rule": {"kind": "Affine", "gain": 1.0, "offset": 0.0},
            },
        )
    assert body["result"]["isError"] is True  # type: ignore[index]


@pytest.mark.contract
def test_mcp_update_asset_partition_rule_tool_returns_iserror_on_invalid_rule_shape() -> None:
    """Aggregation Difference + constituent_count != 2 -> InvalidPartitionRuleError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _setup_pseudoaxis_asset(client, headers)
        body = _call_tool(
            client,
            headers,
            call_id=22,
            name="update_asset_partition_rule",
            arguments={
                "asset_id": str(asset_id),
                "partition_rule": {
                    "kind": "Aggregation",
                    "aggregator_kind": "Difference",
                    "constituent_count": 1,
                },
            },
        )
    assert body["result"]["isError"] is True  # type: ignore[index]


@pytest.mark.contract
def test_mcp_update_asset_partition_rule_tool_returns_iserror_on_unknown_kind() -> None:
    """Unknown partition-rule kind discriminator triggers InvalidPartitionRuleError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = _setup_pseudoaxis_asset(client, headers)
        body = _call_tool(
            client,
            headers,
            call_id=23,
            name="update_asset_partition_rule",
            arguments={
                "asset_id": str(asset_id),
                "partition_rule": {"kind": "NotARealKind"},
            },
        )
    assert body["result"]["isError"] is True  # type: ignore[index]
