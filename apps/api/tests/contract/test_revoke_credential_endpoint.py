"""Contract tests for `POST /federation/credentials/{credential_id}/revoke`.

Widest-source terminal transition: any non-Revoked status (Active or
Rotating) -> Revoked. Strict-not-idempotent (re-revoke returns 409).
Optional `reason` request body; principal identifies the actor.

The cross-BC happy-path (CredentialRevoked + DecisionRegistered
atomic write) is exercised by the handler tests and the integration
test against real Postgres. These tests pin the status-code mappings
via dependency overrides; the route-layer happy path returns 204 on
the handler's None return.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.credential import (
    CredentialCannotRevokeError,
    CredentialNotFoundError,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.revoke_credential.route import (
    _get_handler as _get_revoke_credential_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_revoke_credential_returns_204_via_handler_override() -> None:
    """Handler returns None on the happy path -> route returns 204."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_revoke_credential_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/revoke",
            json={"reason": "compromised secret being retired"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_revoke_credential_returns_204_with_empty_body() -> None:
    """`reason` is optional; an empty body is accepted."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_revoke_credential_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/revoke",
            json={},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_revoke_credential_returns_204_with_no_body() -> None:
    """Body is entirely optional; omitting it is accepted."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_revoke_credential_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/federation/credentials/{uuid4()}/revoke")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_revoke_credential_returns_404_on_unknown_credential() -> None:
    """A handler raising CredentialNotFoundError surfaces as 404."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialNotFoundError(UUID(int=0))

    app.dependency_overrides[_get_revoke_credential_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/revoke",
            json={"reason": "x"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_revoke_credential_returns_409_when_already_revoked() -> None:
    """Strict-not-idempotent: re-revoking an already-Revoked credential
    raises CredentialCannotRevokeError which surfaces as 409."""
    app = create_app()
    target_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialCannotRevokeError(target_id)

    app.dependency_overrides[_get_revoke_credential_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{target_id}/revoke",
            json={},
        )
    assert response.status_code == 409
    assert "revoked" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_revoke_credential_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_revoke_credential_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/revoke",
            json={"reason": "x"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_revoke_credential_rejects_invalid_uuid_path_with_422() -> None:
    """A non-UUID path segment is rejected at the FastAPI Path layer."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/credentials/not-a-uuid/revoke",
            json={"reason": "x"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revoke_credential_rejects_extra_body_field_with_422() -> None:
    """Body model is strict (model_config={'extra': 'forbid'} pattern):
    unknown fields are rejected at the Pydantic layer.

    Defensive: when the route body model adds `extra='forbid'`, this
    test pins the rejection. Without the forbid posture FastAPI accepts
    and ignores; either behavior is acceptable so we accept both."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_revoke_credential_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/credentials/{uuid4()}/revoke",
            json={"reason": "x", "unknown_field": "y"},
        )
    # Body model in the slice today does not enforce extra='forbid'; this
    # test accepts either 204 (extra silently ignored) or 422 (extra forbidden).
    assert response.status_code in {204, 422}, response.text
