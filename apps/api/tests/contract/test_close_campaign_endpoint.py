"""Contract tests for `POST /campaigns/{campaign_id}/close`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.close_campaign.route import (
    _get_handler as _get_close_campaign_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_and_start(client: TestClient) -> str:
    response = client.post(
        "/campaigns",
        json={"name": "test", "intent": "Series", "lead_actor_id": str(uuid4())},
    )
    cid = str(response.json()["campaign_id"])
    client.post(f"/campaigns/{cid}/start")
    return cid


@pytest.mark.contract
def test_post_close_returns_204_on_active_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register_and_start(client)
        response = client.post(f"/campaigns/{cid}/close")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_close_returns_204_on_held_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register_and_start(client)
        client.post(f"/campaigns/{cid}/hold", json={"reason": "r"})
        response = client.post(f"/campaigns/{cid}/close")
    assert response.status_code == 204


@pytest.mark.contract
def test_post_close_returns_404_when_campaign_absent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/campaigns/{uuid4()}/close")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_close_returns_409_on_planned_campaign() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/campaigns",
            json={"name": "x", "intent": "Series", "lead_actor_id": str(uuid4())},
        )
        cid = str(response.json()["campaign_id"])
        closed = client.post(f"/campaigns/{cid}/close")
    assert closed.status_code == 409


@pytest.mark.contract
def test_post_close_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_close_campaign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/campaigns/{uuid4()}/close")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
