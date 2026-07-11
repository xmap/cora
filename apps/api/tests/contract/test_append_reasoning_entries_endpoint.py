"""Contract tests for `POST /decisions/{id}/inferences`."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _good_entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "event_id": str(uuid4()),
        "occurred_at": "2026-05-12T12:00:00+00:00",
        "operation_name": "chat",
        "provider_name": "anthropic",
        "request_model": "claude-opus-4-7",
    }
    base.update(overrides)
    return base


def _seed_decision(client: TestClient) -> str:
    actor_id = client.post("/actors", json={"name": "Test Actor"}).json()["actor_id"]
    return client.post(
        "/decisions",
        json={"decided_by": actor_id, "context": "RecipeApproval", "choice": "Approved"},
    ).json()["decision_id"]


# ---------- Happy path ----------


@pytest.mark.contract
def test_post_reasoning_entries_returns_200_for_single_entry() -> None:
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        response = client.post(
            f"/decisions/{decision_id}/inferences",
            json={"entries": [_good_entry()]},
        )
    assert response.status_code == 200
    assert response.json() == {"event_count": 1}


@pytest.mark.contract
def test_post_reasoning_entries_returns_200_for_batch() -> None:
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        response = client.post(
            f"/decisions/{decision_id}/inferences",
            json={"entries": [_good_entry(), _good_entry(), _good_entry()]},
        )
    assert response.status_code == 200
    assert response.json() == {"event_count": 3}


@pytest.mark.contract
def test_post_reasoning_entries_handles_dedup_silently_on_retry() -> None:
    """Re-issuing the same event_id is a silent no-op via PK dedup;
    response still says event_count=1 (acceptance count, not insertion)."""
    shared_id = str(uuid4())
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        first = client.post(
            f"/decisions/{decision_id}/inferences",
            json={"entries": [_good_entry(event_id=shared_id)]},
        )
        second = client.post(
            f"/decisions/{decision_id}/inferences",
            json={"entries": [_good_entry(event_id=shared_id)]},
        )
    assert first.status_code == 200
    assert second.status_code == 200


@pytest.mark.contract
def test_post_reasoning_entries_accepts_full_otel_field_set() -> None:
    """Round-trip every documented OTel gen_ai.* field through the API.

    agent_id is principal-bound (self-reporting only), so the caller
    identifies itself via X-Principal-Id and attributes the entry to
    that same id."""
    producer_id = str(uuid4())
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        response = client.post(
            f"/decisions/{decision_id}/inferences",
            headers={"X-Principal-Id": producer_id},
            json={
                "entries": [
                    _good_entry(
                        operation_name="execute_tool",
                        provider_name="anthropic",
                        request_model="claude-opus-4-7",
                        duration=1234,
                        response_id="msg_abc",
                        response_model="claude-opus-4-7",
                        request_temperature=0.7,
                        request_top_p=0.95,
                        request_max_tokens=4096,
                        output_type="text",
                        finish_reasons=["end_turn"],
                        input_tokens=512,
                        output_tokens=256,
                        agent_id=producer_id,
                        agent_name="ApprovalAgent",
                        agent_description="Reviews recipes",
                        conversation_id="conv-abc",
                        tool_name="get_dataset",
                        tool_call_id="toolu_xyz",
                        tool_type="Function",
                        messages={"prompt": [{"role": "user", "content": "Approve?"}]},
                    )
                ]
            },
        )
    assert response.status_code == 200


@pytest.mark.contract
def test_post_reasoning_entries_appends_across_multiple_calls() -> None:
    """Lazy open lands on first call; subsequent calls append without
    re-emitting the open event. End-to-end smoke."""
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        first = client.post(
            f"/decisions/{decision_id}/inferences",
            json={"entries": [_good_entry()]},
        )
        second = client.post(
            f"/decisions/{decision_id}/inferences",
            json={"entries": [_good_entry(), _good_entry()]},
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == {"event_count": 2}


# ---------- 404 ----------


@pytest.mark.contract
def test_post_reasoning_entries_returns_404_for_unknown_decision() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/decisions/{uuid4()}/inferences",
            json={"entries": [_good_entry()]},
        )
    assert response.status_code == 404


# ---------- 422 (schema validation) ----------


@pytest.mark.contract
def test_post_reasoning_entries_rejects_empty_batch_with_422() -> None:
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        response = client.post(
            f"/decisions/{decision_id}/inferences",
            json={"entries": []},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_reasoning_entries_rejects_oversize_batch_with_422() -> None:
    """Cap is 100 entries per batch; 101 must reject."""
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        response = client.post(
            f"/decisions/{decision_id}/inferences",
            json={"entries": [_good_entry() for _ in range(101)]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_reasoning_entries_rejects_missing_required_field_with_422() -> None:
    """provider_name + operation_name + request_model are required."""
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        bad = _good_entry()
        del bad["provider_name"]
        response = client.post(
            f"/decisions/{decision_id}/inferences",
            json={"entries": [bad]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_reasoning_entries_rejects_extra_fields_with_422() -> None:
    """`extra: forbid` on both request schemas."""
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        response = client.post(
            f"/decisions/{decision_id}/inferences",
            json={"entries": [{**_good_entry(), "rogue_field": "boom"}]},
        )
    assert response.status_code == 422


# ---------- Agent attribution is principal-bound ----------


@pytest.mark.contract
def test_post_reasoning_entries_rejects_foreign_agent_id_with_403() -> None:
    """An entry attributing spend to an agent other than the calling
    principal is refused: the ledger only accepts self-reported
    agent spend (budget-inflation guard)."""
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        response = client.post(
            f"/decisions/{decision_id}/inferences",
            headers={"X-Principal-Id": str(uuid4())},
            json={
                "entries": [
                    _good_entry(agent_id=str(uuid4()), cost_usd=250.0),
                ]
            },
        )
    assert response.status_code == 403
    assert "self-reported" in response.json()["detail"]


@pytest.mark.contract
def test_post_reasoning_entries_accepts_self_reported_agent_id() -> None:
    producer_id = str(uuid4())
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        response = client.post(
            f"/decisions/{decision_id}/inferences",
            headers={"X-Principal-Id": producer_id},
            json={
                "entries": [
                    _good_entry(agent_id=producer_id, cost_usd=0.002),
                ]
            },
        )
    assert response.status_code == 200
    assert response.json() == {"event_count": 1}
