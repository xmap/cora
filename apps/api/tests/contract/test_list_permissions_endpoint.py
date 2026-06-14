"""Contract tests for `GET /policies/{policy_id}/permissions`.

End-to-end via TestClient(create_app()) so the lifespan wires
in-memory adapters and the full FastAPI dependency graph runs:
- query params parsed by Pydantic
- caller authz invoked (AllowAll → no-op)
- load_policy on the in-memory store
- handler intersects principal eligibility + conduit match with
  policy.permitted_commands
- route maps to ListPermissionsResponse DTO (always carries
  `incomplete: false` at v1)
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.errors import UnauthorizedError
from cora.trust.features.list_permissions.route import (
    _get_handler as _get_list_permissions_handler,  # pyright: ignore[reportPrivateUsage]
)

_CONDUIT = "01900000-0000-7000-8000-00000000aaaa"
_OTHER_CONDUIT = "01900000-0000-7000-8000-00000000bbbb"
_ALLOWED_PRINCIPAL = "01900000-0000-7000-8000-000000000a01"
_OTHER_PRINCIPAL = "01900000-0000-7000-8000-000000000a02"
_SURFACE = str(SYSTEM_HTTP_SURFACE_ID)


def _define_policy(client: TestClient) -> str:
    """Create a Policy via the real define_policy endpoint and return
    its id. Same in-memory app backs both endpoints. The policy binds
    the HTTP Surface (required by define_policy); list_permissions does
    not evaluate the surface, so it doesn't affect these assertions."""
    response = client.post(
        "/policies",
        json={
            "name": "Beam-team",
            "conduit_id": _CONDUIT,
            "permitted_principal_ids": [_ALLOWED_PRINCIPAL],
            "permitted_commands": ["RegisterActor", "DefinePolicy"],
            "surface_id": _SURFACE,
        },
    )
    assert response.status_code == 201
    policy_id: str = response.json()["policy_id"]
    return policy_id


def _list_url(
    policy_id: str,
    *,
    evaluated_principal_id: str = _ALLOWED_PRINCIPAL,
    evaluated_conduit_id: str = _CONDUIT,
) -> str:
    return (
        f"/policies/{policy_id}/permissions"
        f"?evaluated_principal_id={evaluated_principal_id}"
        f"&evaluated_conduit_id={evaluated_conduit_id}"
    )


@pytest.mark.contract
def test_get_permissions_returns_200_with_sorted_commands_when_eligible() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_list_url(policy_id))

    assert response.status_code == 200
    body = response.json()
    assert body["policy_id"] == policy_id
    assert body["evaluated_principal_id"] == _ALLOWED_PRINCIPAL
    assert body["evaluated_conduit_id"] == _CONDUIT
    assert body["permitted_commands"] == ["DefinePolicy", "RegisterActor"]  # sorted
    assert body["incomplete"] is False


@pytest.mark.contract
def test_get_permissions_returns_empty_when_principal_not_permitted() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_list_url(policy_id, evaluated_principal_id=_OTHER_PRINCIPAL))

    assert response.status_code == 200
    body = response.json()
    assert body["permitted_commands"] == []
    assert body["incomplete"] is False


@pytest.mark.contract
def test_get_permissions_returns_empty_when_conduit_does_not_match() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_list_url(policy_id, evaluated_conduit_id=_OTHER_CONDUIT))

    assert response.status_code == 200
    body = response.json()
    assert body["permitted_commands"] == []


@pytest.mark.contract
def test_get_permissions_returns_404_when_policy_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.get(_list_url(missing_id))

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert missing_id in body["detail"]


@pytest.mark.contract
def test_get_permissions_rejects_invalid_policy_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get(_list_url("not-a-uuid"))
    assert response.status_code == 422


@pytest.mark.contract
def test_get_permissions_rejects_missing_evaluated_principal_id_with_422() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(f"/policies/{policy_id}/permissions?evaluated_conduit_id={_CONDUIT}")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_permissions_rejects_invalid_uuid_in_evaluated_principal_with_422() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_list_url(policy_id, evaluated_principal_id="not-a-uuid"))
    assert response.status_code == 422


@pytest.mark.contract
def test_get_permissions_incomplete_field_always_present() -> None:
    """Anti-hook: `incomplete` must be in every response, even at
    v1 when it's always False. Pin the field's presence so a future
    refactor can't drop it."""
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_list_url(policy_id))
    body = response.json()
    assert "incomplete" in body
    assert isinstance(body["incomplete"], bool)


@pytest.mark.contract
def test_get_permissions_returns_403_when_authorize_denies() -> None:
    """Authorize-deny surfaces as 403 with the deny reason in detail.
    Closes gate-review F3: route.py declares 403 in responses= but
    no contract test pinned the mapping. Without this, removing
    `_handle_unauthorized` would silently turn 403s into 500s."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> object:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_list_permissions_handler] = lambda: fake_handler
    with TestClient(app) as client:
        policy_id = str(uuid4())
        response = client.get(_list_url(policy_id))
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_get_permissions_caller_principal_does_not_affect_decision() -> None:
    """Gate-review F5: pin that the SUBJECT of enumeration (query param)
    determines the result, not the caller's principal_id. The caller
    today is SYSTEM_PRINCIPAL_ID (the dev fallback). If the handler were
    using the caller's principal_id by mistake, the policy below would
    return an empty list since SYSTEM isn't in `permitted_principal_ids`.
    Correct behaviour: returns the policy's commands for the named
    subject."""
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)  # permits only _ALLOWED_PRINCIPAL
        # Caller is SYSTEM_PRINCIPAL_ID; subject is _ALLOWED_PRINCIPAL.
        response = client.get(_list_url(policy_id))
    assert response.status_code == 200
    body = response.json()
    assert body["permitted_commands"] == ["DefinePolicy", "RegisterActor"]


@pytest.mark.contract
def test_get_permissions_rejects_invalid_evaluated_conduit_id_with_422() -> None:
    """Gate-review F6 sibling: 422 must fire on both principal_id and
    conduit_id when invalid. Without this, a future Pydantic version
    upgrade that loosens UUID parsing would silently pass garbage in."""
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_list_url(policy_id, evaluated_conduit_id="not-a-uuid"))
    assert response.status_code == 422
