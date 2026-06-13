"""Contract tests for `POST /enclosures/{enclosure_id}/decommission`.

Lifecycle-terminal transition: any Active Enclosure -> Decommissioned.
Strict-not-idempotent: the second call surfaces 409 rather than
silently absorbing the duplicate. `permit_status` is preserved across
decommission as audit trail.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.enclosure.errors import UnauthorizedError
from cora.enclosure.features.decommission_enclosure.handler import Handler
from cora.enclosure.features.decommission_enclosure.route import (
    _get_handler as _get_decommission_enclosure_handler,  # pyright: ignore[reportPrivateUsage]
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


def _register_enclosure(client: TestClient) -> UUID:
    response = client.post(
        "/enclosures",
        json={"name": "2-BM Hutch A", "containing_asset_id": str(uuid4())},
    )
    assert response.status_code == 201
    return UUID(response.json()["enclosure_id"])


@pytest.mark.contract
def test_post_decommission_returns_204_for_active_enclosure() -> None:
    with TestClient(create_app()) as client:
        enclosure_id = _register_enclosure(client)
        response = client.post(
            f"/enclosures/{enclosure_id}/decommission",
            json={"reason": "end-of-life"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_decommission_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/enclosures/{uuid4()}/decommission",
            json={"reason": "r"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_decommission_returns_409_when_already_decommissioned() -> None:
    """Strict-not-idempotent."""
    with TestClient(create_app()) as client:
        enclosure_id = _register_enclosure(client)
        first = client.post(
            f"/enclosures/{enclosure_id}/decommission",
            json={"reason": "first"},
        )
        assert first.status_code == 204
        second = client.post(
            f"/enclosures/{enclosure_id}/decommission",
            json={"reason": "second"},
        )
    assert second.status_code == 409
    assert "is already decommissioned" in second.json()["detail"]


@pytest.mark.contract
def test_post_decommission_rejects_missing_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        enclosure_id = _register_enclosure(client)
        response = client.post(f"/enclosures/{enclosure_id}/decommission", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_decommission_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        enclosure_id = _register_enclosure(client)
        response = client.post(
            f"/enclosures/{enclosure_id}/decommission",
            json={"reason": "a" * (REASON_MAX_LENGTH + 1)},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_decommission_rejects_malformed_enclosure_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures/not-a-uuid/decommission",
            json={"reason": "r"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_decommission_rejects_whitespace_only_reason_with_400() -> None:
    """Whitespace-only reason passes Pydantic min_length=1 but trips the domain VO."""
    with TestClient(create_app()) as client:
        enclosure_id = _register_enclosure(client)
        response = client.post(
            f"/enclosures/{enclosure_id}/decommission",
            json={"reason": "   "},
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_decommission_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    def _override() -> Handler:
        return fake_handler  # type: ignore[return-value]

    app.dependency_overrides[_get_decommission_enclosure_handler] = _override
    with TestClient(app) as client:
        response = client.post(
            f"/enclosures/{uuid4()}/decommission",
            json={"reason": "r"},
        )
    assert response.status_code == 403
