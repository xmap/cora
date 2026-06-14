"""Contract tests for `GET /policies/{policy_id}/evaluate`.

End-to-end via TestClient(create_app()) so the lifespan wires
in-memory adapters and the full FastAPI dependency graph runs:
- subject_* query params parsed by Pydantic
- caller authz invoked (AllowAll → no-op)
- load_policy on the in-memory store
- pure evaluate function returns Allow|Deny
- route maps to EvaluatePolicyResponse DTO

The policy binds the HTTP Surface (`define_policy` requires a real
Surface) and `evaluate` strict-matches it, so an Allow result requires
`evaluated_surface_id == SYSTEM_HTTP_SURFACE_ID`. A mismatched
evaluated surface denies (covered explicitly below).
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID

_CONDUIT = "01900000-0000-7000-8000-00000000aaaa"
_OTHER_CONDUIT = "01900000-0000-7000-8000-00000000bbbb"
_ALLOWED_PRINCIPAL = "01900000-0000-7000-8000-000000000a01"
_OTHER_PRINCIPAL = "01900000-0000-7000-8000-000000000a02"
_SURFACE = str(SYSTEM_HTTP_SURFACE_ID)
_OTHER_SURFACE = "01900000-0000-7000-8000-00000000face"


def _define_policy(client: TestClient) -> str:
    """Create a Policy via the real define_policy endpoint and return
    its id. Same in-memory app instance is used for the subsequent
    evaluate call. The policy binds the HTTP Surface."""
    response = client.post(
        "/policies",
        json={
            "name": "Beam-team",
            "conduit_id": _CONDUIT,
            "permitted_principal_ids": [_ALLOWED_PRINCIPAL],
            "permitted_commands": ["RegisterActor"],
            "surface_id": _SURFACE,
        },
    )
    assert response.status_code == 201
    policy_id: str = response.json()["policy_id"]
    return policy_id


def _evaluate_url(
    policy_id: str,
    *,
    evaluated_principal_id: str = _ALLOWED_PRINCIPAL,
    evaluated_command_name: str = "RegisterActor",
    evaluated_conduit_id: str = _CONDUIT,
    evaluated_surface_id: str = _SURFACE,
) -> str:
    return (
        f"/policies/{policy_id}/evaluate"
        f"?evaluated_principal_id={evaluated_principal_id}"
        f"&evaluated_command_name={evaluated_command_name}"
        f"&evaluated_conduit_id={evaluated_conduit_id}"
        f"&evaluated_surface_id={evaluated_surface_id}"
    )


@pytest.mark.contract
def test_get_evaluate_returns_200_allow_when_subject_matches() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_evaluate_url(policy_id))

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "Allow"
    assert body["reason"] is None


@pytest.mark.contract
def test_get_evaluate_returns_200_deny_when_principal_not_permitted() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_evaluate_url(policy_id, evaluated_principal_id=_OTHER_PRINCIPAL))

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "Deny"
    assert body["reason"] is not None
    assert "principal" in body["reason"].lower()


@pytest.mark.contract
def test_get_evaluate_returns_200_deny_when_command_not_permitted() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_evaluate_url(policy_id, evaluated_command_name="DropDatabase"))

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "Deny"
    assert "command" in body["reason"].lower()


@pytest.mark.contract
def test_get_evaluate_returns_200_deny_when_conduit_does_not_match() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_evaluate_url(policy_id, evaluated_conduit_id=_OTHER_CONDUIT))

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "Deny"
    assert "conduit" in body["reason"].lower()


@pytest.mark.contract
def test_get_evaluate_returns_200_deny_when_surface_does_not_match() -> None:
    """Strict surface matching: the policy binds the HTTP Surface, so an
    evaluated surface that differs denies even when principal, command,
    and conduit all match."""
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_evaluate_url(policy_id, evaluated_surface_id=_OTHER_SURFACE))

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "Deny"
    assert "surface" in body["reason"].lower()


@pytest.mark.contract
def test_get_evaluate_returns_404_when_policy_does_not_exist() -> None:
    """Missing policy → 404 (handler returns None, route maps via HTTPException)."""
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.get(_evaluate_url(missing_id))

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert missing_id in body["detail"]


@pytest.mark.contract
def test_get_evaluate_rejects_invalid_policy_id_with_422() -> None:
    """Path param must parse as UUID — Pydantic rejects 'not-a-uuid'."""
    with TestClient(create_app()) as client:
        response = client.get(_evaluate_url("not-a-uuid"))
    assert response.status_code == 422


@pytest.mark.contract
def test_get_evaluate_rejects_missing_evaluated_principal_id_with_422() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(
            f"/policies/{policy_id}/evaluate"
            f"?evaluated_command_name=RegisterActor&evaluated_conduit_id={_CONDUIT}"
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_get_evaluate_rejects_invalid_uuid_in_subject_principal_with_422() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_evaluate_url(policy_id, evaluated_principal_id="not-a-uuid"))
    assert response.status_code == 422


@pytest.mark.contract
def test_get_evaluate_rejects_empty_evaluated_command_name_with_422() -> None:
    """Pydantic min_length=1 catches empty command strings."""
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        response = client.get(_evaluate_url(policy_id, evaluated_command_name=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_get_evaluate_caller_principal_does_not_affect_decision() -> None:
    """Pin: the SUBJECT of evaluation (query params) determines the
    Allow/Deny. The caller's principal_id (from get_principal_id Depends,
    today SYSTEM_PRINCIPAL_ID) is only used for the BC-level authz
    gate. Mixing the two would be a bug; this test guards against it."""
    with TestClient(create_app()) as client:
        policy_id = _define_policy(client)
        # The caller is SYSTEM_PRINCIPAL_ID (NOT in the policy's
        # permitted_principal_ids); the subject is _ALLOWED_PRINCIPAL.
        # If the handler were using the caller's principal_id by
        # mistake, this would Deny. Correct behaviour: Allow.
        response = client.get(_evaluate_url(policy_id))
    assert response.status_code == 200
    assert response.json()["decision"] == "Allow"
