"""Contract tests for the `record_acquisition` MCP tool.

Happy path seeds a Capturing-bearing Asset on the app's in-memory
AssetLookup (empty by default in the test app) and registers a
Dataset, so the tool resolves both cross-aggregate references and the
Capturing gate passes. Error paths exercise the real stack.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.infrastructure.adapters.in_memory_asset_lookup import InMemoryAssetLookup
from tests.contract._mcp_helpers import open_session, parse_sse_data

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_CAPTURED_AT = datetime(2026, 6, 10, 9, 0, 0, tzinfo=UTC).isoformat()


def _register_dataset(client: TestClient) -> str:
    return client.post(
        "/datasets",
        json={
            "name": "recon.h5",
            "uri": "s3://b/recon.h5",
            "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
            "byte_size": 0,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
    ).json()["dataset_id"]


def _seed_capturing_asset(client: TestClient) -> str:
    asset_id = uuid4()
    lookup = client.app.state.deps.asset_lookup  # type: ignore[attr-defined]
    assert isinstance(lookup, InMemoryAssetLookup)
    lookup.register(
        asset_id=asset_id,
        name="Oryx Detector",
        tier="Device",
        lifecycle="Active",
        family_affordances=frozenset({"Capturing"}),
    )
    return str(asset_id)


@pytest.mark.contract
def test_mcp_lists_record_acquisition_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "record_acquisition" in tool_names


@pytest.mark.contract
def test_mcp_record_acquisition_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register_dataset(client)
        asset_id = _seed_capturing_asset(client)
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "record_acquisition",
                    "arguments": {
                        "dataset_id": dataset_id,
                        "producing_asset_id": asset_id,
                        "captured_at": _CAPTURED_AT,
                        "settings": {"exposure_ms": 200},
                        "evidence": {},
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_record_acquisition_tool_returns_iserror_for_unknown_dataset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "record_acquisition",
                    "arguments": {
                        "dataset_id": str(uuid4()),
                        "producing_asset_id": str(uuid4()),
                        "captured_at": _CAPTURED_AT,
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_record_acquisition_tool_returns_iserror_on_missing_capturing_affordance() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register_dataset(client)
        asset_id = uuid4()
        lookup = client.app.state.deps.asset_lookup  # type: ignore[attr-defined]
        lookup.register(
            asset_id=asset_id,
            name="Non-capturing device",
            tier="Device",
            lifecycle="Active",
            family_affordances=frozenset({"Imageable"}),
        )
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "record_acquisition",
                    "arguments": {
                        "dataset_id": dataset_id,
                        "producing_asset_id": str(asset_id),
                        "captured_at": _CAPTURED_AT,
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "Capturing" in body["result"]["content"][0]["text"]
