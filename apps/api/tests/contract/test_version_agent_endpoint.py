"""Contract tests for `POST /agents/{agent_id}/version`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


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
def test_post_version_returns_204_on_defined_agent() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        response = client.post(f"/agents/{agent_id}/version")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_version_404_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/agents/{uuid4()}/version")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_version_409_when_already_versioned() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        first = client.post(f"/agents/{agent_id}/version")
        assert first.status_code == 204
        second = client.post(f"/agents/{agent_id}/version")
    assert second.status_code == 409


@pytest.mark.contract
def test_post_version_409_when_deprecated() -> None:
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_define_body())
        agent_id = define.json()["agent_id"]
        deprecate = client.post(f"/agents/{agent_id}/deprecate", json={"reason": "Superseded"})
        assert deprecate.status_code == 204
        response = client.post(f"/agents/{agent_id}/version")
    assert response.status_code == 409
