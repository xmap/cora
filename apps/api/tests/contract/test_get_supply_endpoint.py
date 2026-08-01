"""Contract tests for `GET /supplies/{supply_id}`.

Pinned response shape:
`{id, kind, name, facility_code, containing_asset_id, status}` where
`status` is the StrEnum's string value (Unknown / Available /
Degraded / Unavailable / Recovering).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.supply.errors import UnauthorizedError
from cora.supply.features.get_supply.handler import Handler as GetSupplyHandler
from cora.supply.features.get_supply.route import (
    _get_handler as _get_get_supply_handler,  # pyright: ignore[reportPrivateUsage]
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
def test_get_supply_returns_200_with_unknown_status_for_new_supply() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        response = client.get(f"/supplies/{supply_id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": str(supply_id),
        "kind": "LiquidNitrogen",
        "name": "2-BM LN2",
        "facility_code": "cora",
        "containing_asset_id": None,
        "status": "Unknown",
    }


@pytest.mark.contract
def test_get_supply_returns_200_with_available_status_after_mark_available() -> None:
    with TestClient(create_app()) as client:
        supply_id = _register_supply(client)
        mark = client.post(
            f"/supplies/{supply_id}/mark-available",
            json={"reason": "operator walkdown"},
        )
        assert mark.status_code == 204
        response = client.get(f"/supplies/{supply_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "Available"


@pytest.mark.contract
def test_get_supply_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/supplies/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_supply_returns_422_for_malformed_supply_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/supplies/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_supply_returns_403_when_authorize_denies() -> None:
    """Query handlers also flow through Authorize. The route doesn't
    document 403 (queries are typically allow-all in pilot), but the
    BC's `_handle_unauthorized` is wired and must produce 403, not 500."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    def _override() -> GetSupplyHandler:
        return fake_handler  # type: ignore[return-value]

    app.dependency_overrides[_get_get_supply_handler] = _override
    with TestClient(app) as client:
        response = client.get(f"/supplies/{uuid4()}")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
