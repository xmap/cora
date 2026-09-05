"""Contract tests for `POST /agents/{agent_id}/restate-definition`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_REASON = "restated after the brain migration"


def _define_body() -> dict[str, object]:
    """Define via the legacy `model_ref` path, which is what a pre-brain
    stream looks like and therefore what a restatement exists to correct."""
    return {
        "kind": "RunInitiator",
        "name": "Run Initiator",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
    }


def _agent_id(client: TestClient) -> str:
    define = client.post("/agents", json=_define_body())
    assert define.status_code == 201, define.text
    return str(define.json()["agent_id"])


@pytest.mark.contract
def test_restating_a_rule_brain_returns_204() -> None:
    with TestClient(create_app()) as client:
        agent_id = _agent_id(client)
        response = client.post(
            f"/agents/{agent_id}/restate-definition",
            json={"reason": _REASON, "brain": {"kind": "Rule", "rule": "RunInitiator:v1"}},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_restating_a_name_returns_204_and_is_visible_on_get() -> None:
    with TestClient(create_app()) as client:
        agent_id = _agent_id(client)
        response = client.post(
            f"/agents/{agent_id}/restate-definition",
            json={"reason": _REASON, "name": "Campaign Coordinator"},
        )
        assert response.status_code == 204, response.text
        fetched = client.get(f"/agents/{agent_id}")

    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Campaign Coordinator"


@pytest.mark.contract
def test_the_restated_brain_is_visible_on_get() -> None:
    with TestClient(create_app()) as client:
        agent_id = _agent_id(client)
        client.post(
            f"/agents/{agent_id}/restate-definition",
            json={"reason": _REASON, "brain": {"kind": "Rule", "rule": "RunInitiator:v1"}},
        )
        fetched = client.get(f"/agents/{agent_id}")

    body = fetched.json()
    assert body["brain"] == {"kind": "Rule", "model_ref": None, "rule": "RunInitiator:v1"}
    # Sourced from the brain, so a Rule-brained agent reports no model.
    assert body["model_ref"] is None


@pytest.mark.contract
def test_restating_neither_name_nor_brain_returns_422() -> None:
    with TestClient(create_app()) as client:
        agent_id = _agent_id(client)
        response = client.post(
            f"/agents/{agent_id}/restate-definition",
            json={"reason": _REASON},
        )
    assert response.status_code == 422, response.text


@pytest.mark.contract
def test_missing_reason_returns_422() -> None:
    with TestClient(create_app()) as client:
        agent_id = _agent_id(client)
        response = client.post(
            f"/agents/{agent_id}/restate-definition",
            json={"name": "No Reason Given"},
        )
    assert response.status_code == 422, response.text


@pytest.mark.contract
def test_unknown_agent_returns_404() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/agents/{uuid4()}/restate-definition",
            json={"reason": _REASON, "name": "Ghost"},
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_a_brain_whose_payload_disagrees_with_its_kind_returns_400() -> None:
    """A Rule body carrying a model_ref is refused by the VO, not coerced."""
    with TestClient(create_app()) as client:
        agent_id = _agent_id(client)
        response = client.post(
            f"/agents/{agent_id}/restate-definition",
            json={
                "reason": _REASON,
                "brain": {
                    "kind": "Rule",
                    "rule": "RunInitiator:v1",
                    "model_ref": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
                },
            },
        )
    assert response.status_code == 400, response.text


@pytest.mark.contract
def test_restating_a_deprecated_agent_returns_409() -> None:
    with TestClient(create_app()) as client:
        agent_id = _agent_id(client)
        deprecated = client.post(
            f"/agents/{agent_id}/deprecate",
            json={"reason": "Superseded"},
        )
        assert deprecated.status_code in (200, 204), deprecated.text
        response = client.post(
            f"/agents/{agent_id}/restate-definition",
            json={"reason": _REASON, "name": "Too Late"},
        )
    assert response.status_code == 409, response.text
