"""Contract tests for `POST /policies/{policy_id}/revoke-grant`.

Set-membership removal of one principal from a Policy's permitted set.
Silently idempotent at the decider (absent principal -> no event ->
still 204); the only domain rejection is `PolicyNotFoundError` (404).
Required JSON body: `principal_id` (the grant to remove) + `reason`.

The happy-path fold (state shrinks) is exercised by the handler +
Postgres integration tests. These tests pin the status-code mappings
via dependency overrides; the route-layer happy path returns 204 on
the handler's None return.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.trust.aggregates.policy import PolicyNotFoundError
from cora.trust.errors import UnauthorizedError
from cora.trust.features.revoke_grant.route import (
    _get_handler as _get_revoke_grant_handler,  # pyright: ignore[reportPrivateUsage]
)


def _body() -> dict[str, str]:
    return {"principal_id": str(uuid4()), "reason": "agent decommissioned"}


@pytest.mark.contract
def test_post_revoke_grant_returns_204_via_handler_override() -> None:
    """Handler returns None on the happy path -> route returns 204."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_revoke_grant_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/policies/{uuid4()}/revoke-grant", json=_body())
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_revoke_grant_returns_404_on_unknown_policy() -> None:
    """A handler raising PolicyNotFoundError surfaces as 404."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise PolicyNotFoundError(UUID(int=0))

    app.dependency_overrides[_get_revoke_grant_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/policies/{uuid4()}/revoke-grant", json=_body())
    assert response.status_code == 404


@pytest.mark.contract
def test_post_revoke_grant_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_revoke_grant_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/policies/{uuid4()}/revoke-grant", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_revoke_grant_rejects_missing_reason_with_422() -> None:
    """`reason` is required; omitting it is a Pydantic 422."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/policies/{uuid4()}/revoke-grant",
            json={"principal_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revoke_grant_rejects_blank_reason_with_422() -> None:
    """`reason` has min_length=1; an empty string is a Pydantic 422."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/policies/{uuid4()}/revoke-grant",
            json={"principal_id": str(uuid4()), "reason": ""},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revoke_grant_rejects_missing_principal_with_422() -> None:
    """`principal_id` is required; omitting it is a Pydantic 422."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/policies/{uuid4()}/revoke-grant",
            json={"reason": "x"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revoke_grant_rejects_invalid_uuid_path_with_422() -> None:
    """A non-UUID path segment is rejected at the FastAPI Path layer."""
    with TestClient(create_app()) as client:
        response = client.post("/policies/not-a-uuid/revoke-grant", json=_body())
    assert response.status_code == 422
