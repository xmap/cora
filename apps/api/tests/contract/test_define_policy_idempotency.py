"""Contract tests for `Idempotency-Key` support on `POST /policies`.

Same cross-BC `with_idempotency` decorator as `define_zone` /
`define_conduit`. Test keys kept short to stay below the gitleaks
generic-API-key entropy threshold.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID

_CONDUIT = "01900000-0000-7000-8000-00000000aaaa"
_PRINCIPAL = "01900000-0000-7000-8000-000000000a01"


def _body(name: str = "Beam-team") -> dict[str, object]:
    return {
        "name": name,
        "conduit_id": _CONDUIT,
        "permitted_principal_ids": [_PRINCIPAL],
        "permitted_commands": ["RegisterActor"],
        "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
    }


@pytest.mark.contract
def test_post_policies_without_key_creates_distinct_policies_on_each_call() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post("/policies", json=_body())
        r2 = client.post("/policies", json=_body())
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["policy_id"] != r2.json()["policy_id"]


@pytest.mark.contract
def test_post_policies_same_key_and_body_returns_same_policy_id() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "pk-1"}
        r1 = client.post("/policies", json=_body(), headers=headers)
        r2 = client.post("/policies", json=_body(), headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["policy_id"] == r2.json()["policy_id"]


@pytest.mark.contract
def test_post_policies_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "pk-2"}
        r1 = client.post("/policies", json=_body(), headers=headers)
        r2 = client.post("/policies", json=_body(name="Other"), headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_policies_different_keys_create_distinct_policies() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post("/policies", json=_body(), headers={"Idempotency-Key": "pk-A"})
        r2 = client.post("/policies", json=_body(), headers={"Idempotency-Key": "pk-B"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["policy_id"] != r2.json()["policy_id"]


@pytest.mark.contract
def test_post_policies_cached_response_returns_valid_uuid() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "pk-uuid"}
        r1 = client.post("/policies", json=_body(), headers=headers)
        r2 = client.post("/policies", json=_body(), headers=headers)

    UUID(r1.json()["policy_id"])
    UUID(r2.json()["policy_id"])
    assert r1.json()["policy_id"] == r2.json()["policy_id"]
