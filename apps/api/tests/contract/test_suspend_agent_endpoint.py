"""Contract tests for `POST /agents/{agent_id}/suspend`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.shared.text_bounds import REASON_MAX_LENGTH


def _define_body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "kind": "RunDebriefer",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
    }
    base.update(overrides)
    return base


def _define_and_version(client: TestClient) -> str:
    define = client.post("/agents", json=_define_body())
    agent_id = define.json()["agent_id"]
    client.post(f"/agents/{agent_id}/version")
    return agent_id


@pytest.mark.contract
def test_post_suspend_returns_204_on_versioned_agent() -> None:
    with TestClient(create_app()) as client:
        agent_id = _define_and_version(client)
        response = client.post(
            f"/agents/{agent_id}/suspend",
            json={"reason": "cost overrun observed"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_suspend_409_on_defined_agent() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/suspend",
            json={"reason": "noop"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_suspend_409_when_already_suspended() -> None:
    with TestClient(create_app()) as client:
        agent_id = _define_and_version(client)
        first = client.post(f"/agents/{agent_id}/suspend", json={"reason": "first"})
        assert first.status_code == 204
        second = client.post(f"/agents/{agent_id}/suspend", json={"reason": "second"})
    assert second.status_code == 409


@pytest.mark.contract
def test_post_suspend_404_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/agents/{uuid4()}/suspend", json={"reason": "x"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_suspend_422_on_missing_reason() -> None:
    with TestClient(create_app()) as client:
        agent_id = _define_and_version(client)
        response = client.post(f"/agents/{agent_id}/suspend", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_suspend_422_on_over_cap_reason() -> None:
    with TestClient(create_app()) as client:
        agent_id = _define_and_version(client)
        response = client.post(
            f"/agents/{agent_id}/suspend",
            json={"reason": "x" * (REASON_MAX_LENGTH + 1)},
        )
    assert response.status_code == 422
