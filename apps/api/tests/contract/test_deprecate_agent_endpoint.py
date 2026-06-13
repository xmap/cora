"""Contract tests for `POST /agents/{agent_id}/deprecate`."""

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


@pytest.mark.contract
def test_post_deprecate_returns_204_on_defined_agent_with_reason() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/deprecate",
            json={"reason": "model fingerprint changed"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_deprecate_returns_204_with_no_reason() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(f"/agents/{agent_id}/deprecate", json={})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_on_versioned_agent_succeeds() -> None:
    """Deprecate source set is {Defined, Versioned}."""
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        client.post(f"/agents/{agent_id}/version")
        response = client.post(f"/agents/{agent_id}/deprecate", json={})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_404_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/agents/{uuid4()}/deprecate", json={})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_deprecate_409_when_already_deprecated() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        first = client.post(f"/agents/{agent_id}/deprecate", json={})
        assert first.status_code == 204
        second = client.post(f"/agents/{agent_id}/deprecate", json={})
    assert second.status_code == 409


@pytest.mark.contract
def test_post_deprecate_422_on_over_cap_reason() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(
            f"/agents/{agent_id}/deprecate",
            json={"reason": "x" * (REASON_MAX_LENGTH + 1)},
        )
    assert response.status_code == 422
