"""Contract tests for `Idempotency-Key` support on `POST /families`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. Test keys are short to stay below the gitleaks generic-API-
key entropy threshold.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_families_same_name_twice_returns_409() -> None:
    """Family ids are derived from the name, so a second define on the
    same name collides on the deterministic stream (no Idempotency-Key
    to short-circuit it) and returns 409."""
    with TestClient(create_app()) as client:
        r1 = client.post("/families", json={"name": "Tomography", "affordances": []})
        r2 = client.post("/families", json={"name": "Tomography", "affordances": []})
    assert r1.status_code == 201
    assert r2.status_code == 409


@pytest.mark.contract
def test_post_families_same_name_case_insensitive_returns_409() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post("/families", json={"name": "Tomography", "affordances": []})
        r2 = client.post("/families", json={"name": "tomography", "affordances": []})
    assert r1.status_code == 201
    assert r2.status_code == 409


@pytest.mark.contract
def test_post_families_same_key_and_body_returns_same_family_id() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-1"}
        r1 = client.post(
            "/families", json={"name": "Tomography", "affordances": []}, headers=headers
        )
        r2 = client.post(
            "/families", json={"name": "Tomography", "affordances": []}, headers=headers
        )

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["family_id"] == r2.json()["family_id"]


@pytest.mark.contract
def test_post_families_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-2"}
        r1 = client.post(
            "/families", json={"name": "Tomography", "affordances": []}, headers=headers
        )
        r2 = client.post("/families", json={"name": "Other", "affordances": []}, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_families_different_keys_same_name_returns_409() -> None:
    """Distinct Idempotency-Keys gate only the response cache, not
    identity: the same name still derives one stream, so the second
    call collides and returns 409."""
    with TestClient(create_app()) as client:
        r1 = client.post(
            "/families",
            json={"name": "Tomography", "affordances": []},
            headers={"Idempotency-Key": "ck-A"},
        )
        r2 = client.post(
            "/families",
            json={"name": "Tomography", "affordances": []},
            headers={"Idempotency-Key": "ck-B"},
        )
    assert r1.status_code == 201
    assert r2.status_code == 409


@pytest.mark.contract
def test_post_families_cached_response_returns_valid_uuid() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-uuid"}
        r1 = client.post(
            "/families", json={"name": "Tomography", "affordances": []}, headers=headers
        )
        r2 = client.post(
            "/families", json={"name": "Tomography", "affordances": []}, headers=headers
        )

    UUID(r1.json()["family_id"])  # parses
    UUID(r2.json()["family_id"])  # parses
    assert r1.json()["family_id"] == r2.json()["family_id"]
