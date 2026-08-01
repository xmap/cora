"""Contract tests for `GET /campaigns/{campaign_id}`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.get_campaign.route import (
    _get_handler as _get_get_campaign_handler,  # pyright: ignore[reportPrivateUsage]
)


def _seed(client: TestClient, **overrides: object) -> tuple[str, dict[str, object]]:
    body: dict[str, object] = {
        "name": "In-situ heating",
        "intent": "Series",
        "lead_actor_id": str(uuid4()),
        "tags": ["battery", "heating"],
    }
    body.update(overrides)
    response = client.post("/campaigns", json=body)
    assert response.status_code == 201, response.text
    return str(response.json()["campaign_id"]), body


@pytest.mark.contract
def test_get_campaigns_returns_200_with_full_state() -> None:
    with TestClient(create_app()) as client:
        cid, seeded = _seed(client)
        response = client.get(f"/campaigns/{cid}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == cid
    assert body["name"] == "In-situ heating"
    assert body["intent"] == "Series"
    assert body["lead_actor_id"] == seeded["lead_actor_id"]
    assert body["subject_id"] is None
    assert body["description"] is None
    assert body["tags"] == sorted(["battery", "heating"])
    assert body["external_refs"] == []
    assert body["external_id"] is None
    assert body["run_ids"] == []
    assert body["status"] == "Planned"
    assert body["last_status_reason"] is None


@pytest.mark.contract
def test_get_campaigns_returns_404_when_not_found() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/campaigns/{uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_get_campaigns_returns_422_for_malformed_uuid_path_param() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/campaigns/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_campaigns_reflects_active_state_after_start() -> None:
    with TestClient(create_app()) as client:
        cid, _ = _seed(client)
        start = client.post(f"/campaigns/{cid}/start")
        assert start.status_code == 204
        response = client.get(f"/campaigns/{cid}")
    body = response.json()
    assert body["status"] == "Active"


@pytest.mark.contract
def test_get_campaigns_reflects_held_state_and_reason_after_hold() -> None:
    with TestClient(create_app()) as client:
        cid, _ = _seed(client)
        client.post(f"/campaigns/{cid}/start")
        client.post(f"/campaigns/{cid}/hold", json={"reason": "beam down"})
        response = client.get(f"/campaigns/{cid}")
    body = response.json()
    assert body["status"] == "Held"
    assert body["last_status_reason"] == "beam down"


@pytest.mark.contract
def test_get_campaigns_preserves_last_status_reason_after_resume() -> None:
    """Resume preserves the prior Held reason (audit breadcrumb)."""
    with TestClient(create_app()) as client:
        cid, _ = _seed(client)
        client.post(f"/campaigns/{cid}/start")
        client.post(f"/campaigns/{cid}/hold", json={"reason": "beam down"})
        client.post(f"/campaigns/{cid}/resume")
        response = client.get(f"/campaigns/{cid}")
    body = response.json()
    assert body["status"] == "Active"
    assert body["last_status_reason"] == "beam down"


@pytest.mark.contract
def test_get_campaigns_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_get_campaign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/campaigns/{uuid4()}")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
