"""Contract tests for `POST /campaigns/{campaign_id}/declare-steering`."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.declare_campaign_steering.route import (
    _get_handler as _get_declare_steering_handler,  # pyright: ignore[reportPrivateUsage]
)

_OBJECTIVE: dict[str, Any] = {
    "kind": "Satisfy",
    "target_measurement_name": "rotation_center",
    "target_value": 0.0,
}
_SPACE: dict[str, Any] = {"axes": [{"name": "theta", "lower": -5.0, "upper": 5.0}]}


def _body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"objective": _OBJECTIVE, "space": _SPACE}
    base.update(overrides)
    return base


def _register(client: TestClient) -> str:
    response = client.post(
        "/campaigns",
        json={"name": "test", "intent": "Sweep", "lead_actor_id": str(uuid4())},
    )
    return str(response.json()["campaign_id"])


@pytest.mark.contract
def test_post_declare_steering_returns_204_on_planned_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        response = client.post(f"/campaigns/{cid}/declare-steering", json=_body())
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_declare_steering_returns_204_on_active_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/campaigns/{cid}/start")
        response = client.post(f"/campaigns/{cid}/declare-steering", json=_body())
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_declare_steering_returns_404_when_campaign_absent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/campaigns/{uuid4()}/declare-steering", json=_body())
    assert response.status_code == 404


@pytest.mark.contract
def test_post_declare_steering_returns_409_when_campaign_closed() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/campaigns/{cid}/start")
        client.post(f"/campaigns/{cid}/close")
        response = client.post(f"/campaigns/{cid}/declare-steering", json=_body())
    assert response.status_code == 409


@pytest.mark.contract
def test_post_declare_steering_returns_400_on_empty_space() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        response = client.post(f"/campaigns/{cid}/declare-steering", json=_body(space={"axes": []}))
    assert response.status_code in (400, 422)


@pytest.mark.contract
def test_post_declare_steering_returns_400_on_satisfy_without_target() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        response = client.post(
            f"/campaigns/{cid}/declare-steering",
            json=_body(objective={"kind": "Satisfy", "target_measurement_name": "m"}),
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_declare_steering_returns_422_when_objective_missing() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        response = client.post(f"/campaigns/{cid}/declare-steering", json={"space": _SPACE})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_declare_steering_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_declare_steering_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/campaigns/{uuid4()}/declare-steering", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
