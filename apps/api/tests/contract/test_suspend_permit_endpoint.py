"""Contract tests for `POST /federation/permits/{permit_id}/suspend`."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.permit import (
    PermitCannotSuspendError,
    PermitNotFoundError,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.suspend_permit.route import (
    _get_handler as _get_suspend_permit_handler,  # pyright: ignore[reportPrivateUsage]
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


def _register_body(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "peer_facility_code": "aps-2bm",
        "direction": "Outbound",
        "allowed_credential_ids": [str(uuid4())],
        "allowed_payload_types": ["application/vnd.cora.dataset+json"],
        "allowed_artifact_kinds": ["dataset"],
        "abi_tier_floor": "Stable",
        "expires_at": "2030-01-01T00:00:00+00:00",
        "terms": {
            "kind": "Outbound",
            "scopes": [{"kind": "dataset", "name": "alpha", "qualifier": None}],
            "read_scope": "ReadAllArtifacts",
            "onward_action_scope": "ReadOnly",
        },
    }
    base.update(overrides)
    return base


def _register_and_activate(client: TestClient) -> str:
    register = client.post("/federation/permits", json=_register_body())
    assert register.status_code == 201, register.text
    permit_id = register.json()["permit_id"]
    activate = client.post(f"/federation/permits/{permit_id}/activate")
    assert activate.status_code == 204, activate.text
    return permit_id


@pytest.mark.contract
def test_post_suspend_permit_returns_204_on_active_permit() -> None:
    with TestClient(create_app()) as client:
        permit_id = _register_and_activate(client)
        response = client.post(
            f"/federation/permits/{permit_id}/suspend",
            json={"reason": "peer paused outbound sharing pending PII review"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_suspend_permit_returns_204_with_null_reason() -> None:
    """`reason` is optional; an empty body is accepted."""
    with TestClient(create_app()) as client:
        permit_id = _register_and_activate(client)
        response = client.post(
            f"/federation/permits/{permit_id}/suspend",
            json={},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_suspend_permit_returns_409_on_defined_permit() -> None:
    """A freshly-registered (Defined) permit cannot be suspended;
    activate it first."""
    with TestClient(create_app()) as client:
        register = client.post("/federation/permits", json=_register_body())
        permit_id = register.json()["permit_id"]
        response = client.post(
            f"/federation/permits/{permit_id}/suspend",
            json={"reason": "x"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_suspend_permit_returns_409_when_already_suspended() -> None:
    """Strict-not-idempotent: re-suspending raises 409."""
    with TestClient(create_app()) as client:
        permit_id = _register_and_activate(client)
        first = client.post(
            f"/federation/permits/{permit_id}/suspend",
            json={"reason": "first"},
        )
        assert first.status_code == 204
        second = client.post(
            f"/federation/permits/{permit_id}/suspend",
            json={"reason": "second"},
        )
    assert second.status_code == 409


@pytest.mark.contract
def test_post_suspend_permit_returns_404_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/permits/{uuid4()}/suspend",
            json={"reason": "x"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_suspend_permit_rejects_overlong_reason_with_422() -> None:
    """Pydantic enforces max_length=500 BEFORE reaching the decider."""
    with TestClient(create_app()) as client:
        permit_id = _register_and_activate(client)
        response = client.post(
            f"/federation/permits/{permit_id}/suspend",
            json={"reason": "x" * (REASON_MAX_LENGTH + 1)},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_suspend_permit_rejects_invalid_uuid_path_with_422() -> None:
    """A non-UUID path segment is rejected at the FastAPI Path layer."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/federation/permits/not-a-uuid/suspend",
            json={"reason": "x"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_suspend_permit_returns_404_via_dependency_override() -> None:
    """A handler raising PermitNotFoundError surfaces as 404."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise PermitNotFoundError(UUID(int=0))

    app.dependency_overrides[_get_suspend_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/permits/{uuid4()}/suspend",
            json={"reason": "x"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_suspend_permit_returns_409_via_dependency_override() -> None:
    """A handler raising PermitCannotSuspendError surfaces as 409."""
    from cora.federation.aggregates.permit import PermitStatus

    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise PermitCannotSuspendError(UUID(int=1), PermitStatus.DEFINED)

    app.dependency_overrides[_get_suspend_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/permits/{uuid4()}/suspend",
            json={"reason": "x"},
        )
    assert response.status_code == 409
    assert "cannot be suspended" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_suspend_permit_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_suspend_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/permits/{uuid4()}/suspend",
            json={"reason": "x"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
