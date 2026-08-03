"""MCP tool contract tests for the 13 Visit tools.

Consolidated coverage file: covers `register_visit`, `record_visit_arrival`,
`start_visit`, `hold_visit`, `resume_visit`, `complete_visit`,
`cancel_visit`, `abort_visit`, `void_visit`, `check_in_visit`,
`check_out_visit`, `close_visit_presence`, `take_control_of_surface`,
`release_control_of_surface` per the arch-fitness substring-match
rule. Pins the MCP-tool surface: registration, structured output
shape, isError on not-found.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_PLANNED_END = _NOW + timedelta(hours=8)


def _register_visit_via_rest(client: TestClient) -> str:
    visit_id = str(uuid4())
    response = client.post(
        "/visits",
        json={
            "visit_id": visit_id,
            "policy_id": str(uuid4()),
            "surface_id": str(uuid4()),
            "type": "user",
            "planned_start_at": _NOW.isoformat(),
            "planned_end_at": _PLANNED_END.isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return visit_id


_EXPECTED_TOOL_NAMES = {
    "register_visit",
    "record_visit_arrival",
    "start_visit",
    "hold_visit",
    "resume_visit",
    "complete_visit",
    "cancel_visit",
    "abort_visit",
    "void_visit",
    # Presence tools.
    "check_in_visit",
    "check_out_visit",
    "close_visit_presence",
    # Surface-control tools.
    "take_control_of_surface",
    "release_control_of_surface",
}


@pytest.mark.contract
def test_mcp_lists_all_visit_tools_including_presence() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = {t["name"] for t in body["result"]["tools"]}
    missing = _EXPECTED_TOOL_NAMES - tool_names
    assert not missing, f"missing visit tools: {missing}"


@pytest.mark.contract
def test_mcp_register_visit_tool_returns_structured_visit_id() -> None:
    visit_id = str(uuid4())
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "register_visit",
                    "arguments": {
                        "visit_id": visit_id,
                        "policy_id": str(uuid4()),
                        "surface_id": str(uuid4()),
                        "type": "user",
                        "planned_start_at": _NOW.isoformat(),
                        "planned_end_at": _PLANNED_END.isoformat(),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["visit_id"] == visit_id


@pytest.mark.parametrize(
    "tool_name",
    sorted(_EXPECTED_TOOL_NAMES - {"register_visit"}),
)
@pytest.mark.contract
def test_mcp_lifecycle_tool_returns_iserror_when_visit_not_found(tool_name: str) -> None:
    """All non-genesis tools return isError=True when the target Visit doesn't exist."""
    arguments: dict[str, str] = {"visit_id": str(uuid4())}
    if tool_name in {"hold_visit", "cancel_visit", "abort_visit", "void_visit"}:
        arguments["reason"] = "r"
    # Check-in and check-out name no actor: the caller checks itself in or
    # out. close_visit_presence is the exception, and naming the target IS
    # its intent.
    if tool_name == "check_in_visit":
        arguments["mode"] = "physical"
    if tool_name == "close_visit_presence":
        arguments["actor_id"] = str(uuid4())
    # Surface-control tools carry surface_id.
    if tool_name in {"take_control_of_surface", "release_control_of_surface"}:
        arguments["surface_id"] = str(uuid4())

    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_record_visit_arrival_tool_returns_structured_visit_id_on_happy_path() -> None:
    """Spot-check: lifecycle tools also emit `structuredContent` with visit_id."""
    with TestClient(create_app()) as client:
        visit_id = _register_visit_via_rest(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "record_visit_arrival",
                    "arguments": {"visit_id": visit_id},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["visit_id"] == visit_id


@pytest.mark.contract
def test_mcp_presence_tools_report_the_calling_principal_as_the_actor() -> None:
    """Check-in and check-out echo back the CALLER, not a caller-named actor.

    The tools take no `actor_id`, so the only actor they can report is the
    authenticated principal. This drives the success path of both tools, which
    the not-found parametrization above never reaches, and pins the value the
    caller is told was recorded.
    """
    with TestClient(create_app()) as client:
        visit_id = _register_visit_via_rest(client)
        client.post(f"/visits/{visit_id}/record-arrival")
        session_headers = open_session(client)

        checked_in = parse_sse_data(
            client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 10,
                    "method": "tools/call",
                    "params": {
                        "name": "check_in_visit",
                        "arguments": {"visit_id": visit_id, "mode": "physical"},
                    },
                },
                headers=session_headers,
            ).text
        )["result"]

        checked_out = parse_sse_data(
            client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {
                        "name": "check_out_visit",
                        "arguments": {"visit_id": visit_id},
                    },
                },
                headers=session_headers,
            ).text
        )["result"]

    assert checked_in["isError"] is False, checked_in
    assert checked_out["isError"] is False, checked_out
    assert checked_in["structuredContent"]["visit_id"] == visit_id
    assert checked_out["structuredContent"]["visit_id"] == visit_id
    # Both halves must name the same actor: whoever called them.
    assert (
        checked_in["structuredContent"]["actor_id"] == checked_out["structuredContent"]["actor_id"]
    )
