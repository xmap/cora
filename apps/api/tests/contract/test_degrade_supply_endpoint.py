"""Contract tests for `POST /supplies/{supply_id}/degrade` (10a-b)."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.errors import UnauthorizedError
from cora.supply.features.degrade_supply.handler import Handler
from cora.supply.features.degrade_supply.route import (
    _get_handler as _get_degrade_supply_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_and_mark_available(client: TestClient) -> UUID:
    response = client.post(
        "/supplies",
        json={
            "kind": "LiquidNitrogen",
            "name": "2-BM LN2",
            "facility_code": "cora",
        },
    )
    assert response.status_code == 201
    supply_id = UUID(response.json()["supply_id"])
    mark = client.post(
        f"/supplies/{supply_id}/mark-available",
        json={"reason": "walkdown"},
    )
    assert mark.status_code == 204
    return supply_id


@pytest.mark.contract
def test_post_degrade_returns_204_for_available_supply() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_and_mark_available(client)
        response = client.post(
            f"/supplies/{supply_id}/degrade",
            json={"reason": "half-current"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_degrade_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/supplies/{uuid4()}/degrade", json={"reason": "r"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_degrade_returns_409_when_already_degraded() -> None:
    """Strict-not-idempotent: re-degrading raises."""
    with TestClient(create_app()) as client:
        supply_id = _register_and_mark_available(client)
        first = client.post(f"/supplies/{supply_id}/degrade", json={"reason": "first"})
        assert first.status_code == 204
        second = client.post(f"/supplies/{supply_id}/degrade", json={"reason": "second"})
    assert second.status_code == 409
    assert "cannot be degraded" in second.json()["detail"].lower()


@pytest.mark.contract
def test_post_degrade_rejects_missing_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_and_mark_available(client)
        response = client.post(f"/supplies/{supply_id}/degrade", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_degrade_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_and_mark_available(client)
        response = client.post(
            f"/supplies/{supply_id}/degrade",
            json={"reason": "a" * (REASON_MAX_LENGTH + 1)},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_degrade_rejects_whitespace_only_reason_with_400() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_and_mark_available(client)
        response = client.post(f"/supplies/{supply_id}/degrade", json={"reason": "   "})
    assert response.status_code == 400


@pytest.mark.contract
def test_post_degrade_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    def _override() -> Handler:
        return fake_handler  # type: ignore[return-value]

    app.dependency_overrides[_get_degrade_supply_handler] = _override
    with TestClient(app) as client:
        response = client.post(f"/supplies/{uuid4()}/degrade", json={"reason": "r"})
    assert response.status_code == 403
