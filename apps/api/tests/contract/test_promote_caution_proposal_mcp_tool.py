"""Contract tests for the `promote_caution_proposal` MCP tool."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.agent.seed_caution_drafter import (
    CAUTION_DRAFTER_AGENT_ID,
    seed_caution_drafter_agent,
)
from cora.api.main import create_app
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_CAUTION_PROPOSAL,
    DecisionConfidenceSource,
    DecisionRegistered,
    event_type_name,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.contract._mcp_helpers import open_session, parse_sse_data

_T0 = datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC)
_ASSET_ID = UUID("01900000-0000-7000-8000-000000000aab")
_TEST_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000099aab")

_PROPOSED_CAUTION_NOTICE: dict[str, Any] = {
    "target_kind": "Asset",
    "target_id": str(_ASSET_ID),
    "category": "Wear",
    "severity": "Notice",
    "title": "MCP contract-test Caution",
    "body": (
        "MCP contract-test body that spans enough characters to satisfy "
        "the schema's minLength constraint on the body field."
    ),
    "tags": ["mcp-test"],
}


async def _seed_caution_proposal_decision(
    app: FastAPI,
    *,
    decision_id: UUID,
    choice: str = "ProposeNotice",
    inputs: dict[str, Any] | None = None,
) -> None:
    """Append a CautionProposal Decision via the app's wired kernel.

    Seeds the canonical CautionDrafter Agent and uses its id as the
    Decision's `actor_id` so the provenance gate passes.
    """
    deps = app.state.deps
    await seed_caution_drafter_agent(deps)
    actor_id = CAUTION_DRAFTER_AGENT_ID
    event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(actor_id),
        context=DECISION_CONTEXT_CAUTION_PROPOSAL,
        choice=choice,
        parent_id=None,
        override_kind=None,
        rule="agent:CautionDrafter:v1",
        reasoning="mcp contract-test rationale narrative; long enough for the validator",
        confidence=0.7,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        inputs=inputs if inputs is not None else {"proposed_caution": _PROPOSED_CAUTION_NOTICE},
        reasoning_signature=None,
        occurred_at=_T0,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_T0,
        event_id=uuid4(),
        command_name="CautionDrafterSubscriber",
        correlation_id=_TEST_CORRELATION_ID,
        causation_id=None,
        principal_id=actor_id,
    )
    await deps.event_store.append(
        stream_type="Decision",
        stream_id=decision_id,
        expected_version=0,
        events=[new_event],
    )


# ---------------------------------------------------------------------------
# tools/list surface
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_mcp_lists_promote_caution_proposal_tool() -> None:
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
    assert "promote_caution_proposal" in tool_names


@pytest.mark.contract
def test_mcp_promote_caution_proposal_advertises_signature() -> None:
    """Tool schema declares `decision_id` (required UUID)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool = next(t for t in body["result"]["tools"] if t["name"] == "promote_caution_proposal")
    assert "CautionDrafter" in tool["description"]
    properties = tool["inputSchema"]["properties"]
    assert "decision_id" in properties
    required = tool["inputSchema"].get("required", [])
    assert "decision_id" in required


# ---------------------------------------------------------------------------
# tools/call: happy path returns structured output
# ---------------------------------------------------------------------------


@pytest.mark.contract
async def test_mcp_promote_caution_proposal_returns_structured_caution_id() -> None:
    """Happy path: tools/call dispatches register_caution and the MCP
    structuredContent carries both decision_id (echoed) and caution_id (new)."""
    with TestClient(create_app()) as client:
        decision_id = uuid4()
        await _seed_caution_proposal_decision(cast("FastAPI", client.app), decision_id=decision_id)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "promote_caution_proposal",
                    "arguments": {"decision_id": str(decision_id)},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    structured = result["structuredContent"]
    assert structured["decision_id"] == str(decision_id)
    # caution_id is a UUID string (parseable).
    UUID(structured["caution_id"])


# ---------------------------------------------------------------------------
# tools/call: error surfacing
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_mcp_promote_unknown_decision_surfaces_iserror() -> None:
    """DecisionNotFoundError (raised by load_decision) surfaces as MCP isError."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "promote_caution_proposal",
                    "arguments": {"decision_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
async def test_mcp_promote_no_action_decision_surfaces_iserror() -> None:
    """NoAction is non-actionable; the tool surfaces the 400-equivalent
    as MCP isError."""
    with TestClient(create_app()) as client:
        decision_id = uuid4()
        await _seed_caution_proposal_decision(
            cast("FastAPI", client.app),
            decision_id=decision_id,
            choice="NoAction",
            inputs={"reason": "no actionable signal"},
        )
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "promote_caution_proposal",
                    "arguments": {"decision_id": str(decision_id)},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
