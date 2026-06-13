"""Contract tests for `POST /supplies/{supply_id}/mark-recovering` (10a-b)."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.errors import UnauthorizedError
from cora.supply.features.mark_supply_recovering.handler import Handler
from cora.supply.features.mark_supply_recovering.route import (
    _get_handler as _get_mark_supply_recovering_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_and_mark_unavailable(client: TestClient) -> UUID:
    """Get a Supply into the Unavailable state (single-source for mark_recovering)."""
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
    mark = client.post(f"/supplies/{supply_id}/mark-unavailable", json={"reason": "beam dump"})
    assert mark.status_code == 204
    return supply_id


@pytest.mark.contract
def test_post_mark_recovering_returns_204_for_unavailable_supply() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_and_mark_unavailable(client)
        response = client.post(
            f"/supplies/{supply_id}/mark-recovering",
            json={"reason": "beam returning"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_mark_recovering_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/supplies/{uuid4()}/mark-recovering", json={"reason": "r"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_mark_recovering_returns_409_when_supply_is_unknown() -> None:
    """Single-source: only Unavailable can be marked Recovering."""
    with TestClient(create_app()) as client:
        register = client.post(
            "/supplies",
            json={
                "kind": "X",
                "name": "Y",
                "facility_code": "cora",
            },
        )
        supply_id = UUID(register.json()["supply_id"])
        response = client.post(f"/supplies/{supply_id}/mark-recovering", json={"reason": "r"})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_mark_recovering_rejects_missing_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_and_mark_unavailable(client)
        response = client.post(f"/supplies/{supply_id}/mark-recovering", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_recovering_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_and_mark_unavailable(client)
        response = client.post(
            f"/supplies/{supply_id}/mark-recovering",
            json={"reason": "a" * (REASON_MAX_LENGTH + 1)},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_recovering_rejects_malformed_supply_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/supplies/not-a-uuid/mark-recovering", json={"reason": "r"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_recovering_rejects_whitespace_only_reason_with_400() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_and_mark_unavailable(client)
        response = client.post(f"/supplies/{supply_id}/mark-recovering", json={"reason": "   "})
    assert response.status_code == 400


@pytest.mark.contract
def test_post_mark_recovering_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    def _override() -> Handler:
        return fake_handler  # type: ignore[return-value]

    app.dependency_overrides[_get_mark_supply_recovering_handler] = _override
    with TestClient(app) as client:
        response = client.post(f"/supplies/{uuid4()}/mark-recovering", json={"reason": "r"})
    assert response.status_code == 403
