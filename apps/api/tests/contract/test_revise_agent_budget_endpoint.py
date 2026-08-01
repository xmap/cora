"""Contract tests for `POST /agents/{agent_id}/budget`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_body() -> dict[str, object]:
    return {
        "kind": "RunDebriefer",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
    }


@pytest.mark.contract
def test_post_revise_budget_returns_204_with_both_caps() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/budget",
            json={"monthly_usd_cap": 100.0, "daily_token_cap": 500000},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_revise_budget_returns_204_with_only_one_cap() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/budget",
            json={"monthly_usd_cap": 50.0},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_revise_budget_clears_with_empty_body() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(
            f"/agents/{agent_id}/budget",
            json={"monthly_usd_cap": 100.0, "daily_token_cap": 100000},
        )
        response = client.post(f"/agents/{agent_id}/budget", json={})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_revise_budget_404_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/agents/{uuid4()}/budget", json={"monthly_usd_cap": 10.0})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_revise_budget_409_on_deprecated_agent() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(f"/agents/{agent_id}/deprecate", json={"reason": "Superseded"})
        response = client.post(f"/agents/{agent_id}/budget", json={"monthly_usd_cap": 10.0})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_revise_budget_422_on_negative_monthly_cap() -> None:
    """Pydantic ge=0 enforces non-negative caps at the route layer."""
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(f"/agents/{agent_id}/budget", json={"monthly_usd_cap": -1.0})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revise_budget_422_on_negative_daily_token_cap() -> None:
    """Pydantic ge=0 on daily_token_cap regresses independently of monthly."""
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(f"/agents/{agent_id}/budget", json={"daily_token_cap": -1})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revise_budget_idempotent_returns_204_on_same_caps() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        first = client.post(
            f"/agents/{agent_id}/budget",
            json={"monthly_usd_cap": 50.0, "daily_token_cap": 100000},
        )
        second = client.post(
            f"/agents/{agent_id}/budget",
            json={"monthly_usd_cap": 50.0, "daily_token_cap": 100000},
        )
    assert first.status_code == 204
    assert second.status_code == 204
