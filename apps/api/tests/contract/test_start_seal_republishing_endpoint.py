"""Contract tests for `POST /federation/seals/{facility_code}/republishing/start`.

The happy-path Live -> Republishing transition is exercised end-to-end
in the handler tests; here we pin the status-code mappings via
dependency overrides plus Pydantic-layer rejection (extra fields under
`extra=forbid`).
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.seal import (
    SealCannotStartRepublishingError,
    SealNotFoundError,
    SealStatus,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.start_seal_republishing.route import (
    _get_handler as _get_start_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_start_seal_republishing_returns_204_via_handler_override() -> None:
    """Handler returns None on the happy path -> route returns 204."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/republishing/start",
            json={"reason": "root rotation drill"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_start_seal_republishing_returns_204_without_reason() -> None:
    """`reason` is optional; an absent value is accepted."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/republishing/start",
            json={},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_start_seal_republishing_returns_204_with_empty_body() -> None:
    """A POST with no body still succeeds (body is optional via default-None reason)."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/republishing/start",
            json={"reason": None},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_start_seal_republishing_returns_404_on_uninitialized_seal() -> None:
    """A handler raising SealNotFoundError surfaces as 404."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealNotFoundError("aps-2bm")

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/republishing/start",
            json={},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_start_seal_republishing_returns_409_when_republishing() -> None:
    """A handler raising SealCannotStartRepublishingError surfaces as 409."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCannotStartRepublishingError("aps-2bm", SealStatus.REPUBLISHING)

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/republishing/start",
            json={},
        )
    assert response.status_code == 409
    assert "cannot start republishing" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_start_seal_republishing_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-2bm/republishing/start",
            json={},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_start_seal_republishing_rejects_extra_field_with_422() -> None:
    """`extra=forbid` on the request body schema rejects unknown fields."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/seals/aps-2bm/republishing/start",
            json={"reason": "root rotation drill", "unexpected_field": "boom"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_start_seal_republishing_accepts_uuid_shaped_facility_code() -> None:
    """The path parameter is a free-form str, including UUID-shaped values."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_start_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{UUID(int=1)}/republishing/start",
            json={},
        )
    assert response.status_code == 204, response.text
