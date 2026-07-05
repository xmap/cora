"""HTTP contract test for the `revoke_grant` endpoint.

Pins the REST surface at `POST /policies/{policy_id}/revoke-grant`: 204 happy
path, 404 unknown policy, 400 blank reason, and the silently-idempotent noop
(revoking an already-absent principal still returns 204). Policies are seeded
via `define_policy`'s `POST /policies`.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID

_CONDUIT = "01900000-0000-7000-8000-00000000aaaa"
_PRINCIPAL = "01900000-0000-7000-8000-000000000a01"


def _define_policy(client: TestClient) -> str:
    """Define a policy granting `_PRINCIPAL`; return its id."""
    response = client.post(
        "/policies",
        json={
            "name": "Beam-team",
            "conduit_id": _CONDUIT,
            "permitted_principal_ids": [_PRINCIPAL],
            "permitted_commands": ["RegisterActor"],
            "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["policy_id"]


@pytest.mark.contract
def test_revoke_grant_returns_204_for_present_principal() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.post(
            f"/policies/{policy_id}/revoke-grant",
            json={"permitted_principal_id": _PRINCIPAL, "reason": "access review"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_revoke_grant_returns_204_for_absent_principal_silent_idempotent() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.post(
            f"/policies/{policy_id}/revoke-grant",
            json={"permitted_principal_id": str(uuid4()), "reason": "access review"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_revoke_grant_returns_404_when_policy_absent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/policies/{uuid4()}/revoke-grant",
            json={"permitted_principal_id": _PRINCIPAL, "reason": "access review"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_revoke_grant_returns_400_on_whitespace_only_reason() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.post(
            f"/policies/{policy_id}/revoke-grant",
            json={"permitted_principal_id": _PRINCIPAL, "reason": "   "},
        )
    assert response.status_code == 400
