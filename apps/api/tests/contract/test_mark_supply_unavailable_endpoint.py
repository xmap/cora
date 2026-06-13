"""Contract tests for `POST /supplies/{supply_id}/mark-unavailable` (10a-b)."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.errors import UnauthorizedError
from cora.supply.features.mark_supply_unavailable.handler import Handler
from cora.supply.features.mark_supply_unavailable.route import (
    _get_handler as _get_mark_supply_unavailable_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_supply(client: TestClient) -> UUID:
    response = client.post(
        "/supplies",
        json={
            "kind": "LiquidNitrogen",
            "name": "2-BM LN2",
            "facility_code": "cora",
        },
    )
    assert response.status_code == 201
    return UUID(response.json()["supply_id"])


@pytest.mark.contract
def test_post_mark_unavailable_returns_204_for_unknown_supply() -> None:
    """Unknown is in the source set (widest source set of any transition)."""
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        response = client.post(
            f"/supplies/{supply_id}/mark-unavailable", json={"reason": "beam dump"}
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_mark_unavailable_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/supplies/{uuid4()}/mark-unavailable", json={"reason": "r"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_mark_unavailable_returns_409_when_already_unavailable() -> None:
    """Strict-not-idempotent."""
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        first = client.post(f"/supplies/{supply_id}/mark-unavailable", json={"reason": "first"})
        assert first.status_code == 204
        second = client.post(f"/supplies/{supply_id}/mark-unavailable", json={"reason": "second"})
    assert second.status_code == 409


@pytest.mark.contract
def test_post_mark_unavailable_rejects_missing_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        response = client.post(f"/supplies/{supply_id}/mark-unavailable", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_unavailable_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        response = client.post(
            f"/supplies/{supply_id}/mark-unavailable",
            json={"reason": "a" * (REASON_MAX_LENGTH + 1)},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_unavailable_rejects_malformed_supply_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/supplies/not-a-uuid/mark-unavailable", json={"reason": "r"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_unavailable_rejects_whitespace_only_reason_with_400() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        response = client.post(f"/supplies/{supply_id}/mark-unavailable", json={"reason": "   "})
    assert response.status_code == 400


@pytest.mark.contract
def test_post_mark_unavailable_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    def _override() -> Handler:
        return fake_handler  # type: ignore[return-value]

    app.dependency_overrides[_get_mark_supply_unavailable_handler] = _override
    with TestClient(app) as client:
        response = client.post(f"/supplies/{uuid4()}/mark-unavailable", json={"reason": "r"})
    assert response.status_code == 403
