"""Contract tests for `POST /supplies/{supply_id}/mark-available`."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.errors import UnauthorizedError
from cora.supply.features.mark_supply_available.handler import (
    Handler as MarkAvailableHandler,
)
from cora.supply.features.mark_supply_available.route import (
    _get_handler as _get_mark_available_handler,  # pyright: ignore[reportPrivateUsage]
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
def test_post_mark_available_returns_204_for_unknown_supply() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        response = client.post(
            f"/supplies/{supply_id}/mark-available",
            json={"reason": "operator walkdown confirms LN2 flowing"},
        )
    assert response.status_code == 204
    assert response.text == ""


@pytest.mark.contract
def test_post_mark_available_returns_404_for_unknown_supply_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/supplies/{uuid4()}/mark-available",
            json={"reason": "r"},
        )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_mark_available_returns_409_when_re_marking() -> None:
    """Strict-not-idempotent: second call raises SupplyCannotMarkAvailableError."""
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        first = client.post(f"/supplies/{supply_id}/mark-available", json={"reason": "first"})
        assert first.status_code == 204
        second = client.post(f"/supplies/{supply_id}/mark-available", json={"reason": "second"})
    assert second.status_code == 409
    assert "cannot be marked available" in second.json()["detail"].lower()


@pytest.mark.contract
def test_post_mark_available_rejects_missing_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        response = client.post(f"/supplies/{supply_id}/mark-available", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_available_rejects_empty_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        response = client.post(f"/supplies/{supply_id}/mark-available", json={"reason": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_available_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        response = client.post(
            f"/supplies/{supply_id}/mark-available",
            json={"reason": "a" * (REASON_MAX_LENGTH + 1)},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_available_rejects_whitespace_only_reason_with_400() -> None:
    """Whitespace-only passes Pydantic min_length=1 but trips SupplyReason VO."""
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        response = client.post(f"/supplies/{supply_id}/mark-available", json={"reason": "   "})
    assert response.status_code == 400
    assert "Supply transition reason" in response.json()["detail"]


@pytest.mark.contract
def test_post_mark_available_rejects_malformed_supply_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/supplies/not-a-uuid/mark-available", json={"reason": "r"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_available_returns_403_when_authorize_denies() -> None:
    """Route documents 403 in `responses=`; this pins the wire-level path."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    def _override() -> MarkAvailableHandler:
        return fake_handler  # type: ignore[return-value]

    app.dependency_overrides[_get_mark_available_handler] = _override
    with TestClient(app) as client:
        response = client.post(f"/supplies/{uuid4()}/mark-available", json={"reason": "r"})
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
