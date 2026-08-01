"""Contract tests for `POST /campaigns/{campaign_id}/abandon`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.abandon_campaign.route import (
    _get_handler as _get_abandon_campaign_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register(client: TestClient) -> str:
    response = client.post(
        "/campaigns",
        json={"name": "test", "intent": "Series", "lead_actor_id": str(uuid4())},
    )
    return str(response.json()["campaign_id"])


@pytest.mark.contract
def test_post_abandon_returns_204_on_planned_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        response = client.post(
            f"/campaigns/{cid}/abandon",
            json={"reason": "proposal cancelled"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_abandon_returns_204_on_active_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/campaigns/{cid}/start")
        response = client.post(
            f"/campaigns/{cid}/abandon",
            json={"reason": "instrument failure"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_abandon_returns_204_on_held_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/campaigns/{cid}/start")
        client.post(f"/campaigns/{cid}/hold", json={"reason": "r"})
        response = client.post(
            f"/campaigns/{cid}/abandon",
            json={"reason": "no recovery in window"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_abandon_returns_404_when_campaign_absent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/campaigns/{uuid4()}/abandon",
            json={"reason": "r"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_abandon_returns_409_on_already_closed_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/campaigns/{cid}/start")
        client.post(f"/campaigns/{cid}/close")
        response = client.post(
            f"/campaigns/{cid}/abandon",
            json={"reason": "r"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_abandon_returns_400_on_whitespace_only_reason() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        response = client.post(f"/campaigns/{cid}/abandon", json={"reason": "   "})
    assert response.status_code == 400
    assert "Campaign abandon reason" in response.json()["detail"]


@pytest.mark.contract
def test_post_abandon_returns_422_when_reason_missing() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        response = client.post(f"/campaigns/{cid}/abandon", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_abandon_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_abandon_campaign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/campaigns/{uuid4()}/abandon",
            json={"reason": "r"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
