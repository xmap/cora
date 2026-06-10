"""Contract tests for `GET /federation/credentials/{credential_id}`.

200 + opaque-pointer hygiene + lifecycle-timestamp shape; 404 on
miss; 422 on malformed path uuid; 403 on Authorize-port denial.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.errors import UnauthorizedError
from cora.federation.features.get_credential.route import (
    _get_handler as _get_get_credential_handler,  # pyright: ignore[reportPrivateUsage]
)

_EXPIRES_AT_DT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = _EXPIRES_AT_DT.isoformat()


def _seed(client: TestClient, **overrides: object) -> tuple[str, dict[str, Any]]:
    body: dict[str, Any] = {
        "facility_code": "aps-2bm",
        "audience": "peer.example.org",
        "purpose": "Signing",
        "secret_ref": "vault://kv/cora/federation/aps-2bm/signing#v1",
        "public_material_ref": "vault://kv/cora/federation/aps-2bm/signing/pub#v1",
        "expires_at": _EXPIRES_AT,
    }
    body.update(overrides)
    response = client.post("/federation/credentials", json=body)
    assert response.status_code == 201, response.text
    return str(response.json()["credential_id"]), body


@pytest.mark.contract
def test_get_federation_credential_returns_200_with_full_state() -> None:
    with TestClient(create_app()) as client:
        cid, seeded = _seed(client)
        response = client.get(f"/federation/credentials/{cid}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == cid
    assert body["facility_code"] == seeded["facility_code"]
    assert body["audience"] == seeded["audience"]
    assert body["purpose"] == "Signing"
    assert body["secret_ref"] == seeded["secret_ref"]
    assert body["public_material_ref"] == seeded["public_material_ref"]
    assert datetime.fromisoformat(body["expires_at"]) == _EXPIRES_AT_DT
    assert body["status"] == "Active"
    assert body["rotation_pending_secret_ref"] is None
    assert body["rotation_pending_public_material_ref"] is None
    # `registered_at` is aggregate-state-sourced (folded from
    # CredentialRegistered.occurred_at by the fold-symmetry refactor),
    # so it is always populated regardless of projection backend.
    assert datetime.fromisoformat(body["registered_at"]) is not None
    # `rotation_started_at` stays None when no rotation has occurred.
    assert body["rotation_started_at"] is None


@pytest.mark.contract
def test_get_federation_credential_accepts_optional_field_omission() -> None:
    """public_material_ref and expires_at are nullable on the wire."""
    body: dict[str, Any] = {
        "facility_code": "aps-2bm",
        "audience": "peer.example.org",
        "purpose": "Signing",
        "secret_ref": "vault://kv/cora/federation/aps-2bm/signing#v1",
    }
    with TestClient(create_app()) as client:
        post_response = client.post("/federation/credentials", json=body)
        assert post_response.status_code == 201, post_response.text
        cid = post_response.json()["credential_id"]
        response = client.get(f"/federation/credentials/{cid}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["public_material_ref"] is None
    assert payload["expires_at"] is None


@pytest.mark.contract
def test_get_federation_credential_returns_404_when_not_found() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/federation/credentials/{uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_get_federation_credential_returns_422_for_malformed_uuid_path_param() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/credentials/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_federation_credential_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_get_credential_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/federation/credentials/{uuid4()}")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
