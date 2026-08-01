"""Contract tests for `POST /campaigns/{campaign_id}/hold`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.hold_campaign.route import (
    _get_handler as _get_hold_campaign_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_and_start(client: TestClient) -> str:
    response = client.post(
        "/campaigns",
        json={
            "name": "test",
            "intent": "Series",
            "lead_actor_id": str(uuid4()),
        },
    )
    cid = str(response.json()["campaign_id"])
    client.post(f"/campaigns/{cid}/start")
    return cid


@pytest.mark.contract
def test_post_hold_returns_204_on_active_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register_and_start(client)
        response = client.post(
            f"/campaigns/{cid}/hold",
            json={"reason": "beam interruption"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_hold_returns_404_when_campaign_absent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/campaigns/{uuid4()}/hold",
            json={"reason": "r"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_hold_returns_409_when_campaign_is_planned() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/campaigns",
            json={"name": "x", "intent": "Series", "lead_actor_id": str(uuid4())},
        )
        cid = str(response.json()["campaign_id"])
        held = client.post(f"/campaigns/{cid}/hold", json={"reason": "r"})
    assert held.status_code == 409


@pytest.mark.contract
def test_post_hold_returns_400_on_whitespace_only_reason() -> None:
    with TestClient(create_app()) as client:
        cid = _register_and_start(client)
        response = client.post(f"/campaigns/{cid}/hold", json={"reason": "   "})
    # Pydantic's min_length=1 trips first on whitespace-empty? Let's check:
    # min_length=1 counts characters; "   " has 3 chars, passes Pydantic
    # but trips domain VO -> 400.
    assert response.status_code == 400
    assert "Campaign hold reason" in response.json()["detail"]


@pytest.mark.contract
def test_post_hold_returns_422_when_reason_missing() -> None:
    with TestClient(create_app()) as client:
        cid = _register_and_start(client)
        response = client.post(f"/campaigns/{cid}/hold", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_hold_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_hold_campaign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/campaigns/{uuid4()}/hold",
            json={"reason": "r"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
