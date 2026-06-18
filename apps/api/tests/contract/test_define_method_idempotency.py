"""Contract tests for `Idempotency-Key` support on `POST /methods`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. The needed_family_ids frozenset is normalized through
`_normalize_for_hash` (Trust 3c precedent) so reordered input
produces the same hash, and same body returns the same method_id.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


@pytest.mark.contract
def test_post_methods_without_key_creates_distinct_methods_on_each_call() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        r1 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "XRF Mapping",
                "capability_id": _cap_id,
                "needed_family_ids": [],
            },
        )
        r2 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "XRF Mapping",
                "capability_id": _cap_id,
                "needed_family_ids": [],
            },
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["method_id"] != r2.json()["method_id"]


@pytest.mark.contract
def test_post_methods_same_key_and_body_returns_same_method_id() -> None:
    cap1 = str(uuid4())
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        body = {
            "execution_pattern": "Batch",
            "name": "XRF Mapping",
            "capability_id": _cap_id,
            "needed_family_ids": [cap1],
        }
        headers = {"Idempotency-Key": "mk-1"}
        r1 = client.post("/methods", json=body, headers=headers)
        r2 = client.post("/methods", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["method_id"] == r2.json()["method_id"]


@pytest.mark.contract
def test_post_methods_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        headers = {"Idempotency-Key": "mk-2"}
        r1 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "XRF Mapping",
                "capability_id": _cap_id,
                "needed_family_ids": [],
            },
            headers=headers,
        )
        r2 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "Other",
                "capability_id": _cap_id,
                "needed_family_ids": [],
            },
            headers=headers,
        )

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_methods_same_key_different_capability_id_returns_422() -> None:
    """Cross-BC additive payload safety pin (gate-review P1): same
    Idempotency-Key + same `name`/`needed_family_ids` BUT different
    `capability_id` must surface as 422 (hash collision detection).
    `_normalize_for_hash` SHA256s the full DefineMethod dataclass
    including the `capability_id` field, so the two bodies hash
    differently and the second retry is rejected.

    Pinned because adding the `capability_id` key creates a new
    dimension where idempotency-key conflicts can land; without this
    pin a future regression that omits `capability_id` from
    `_normalize_for_hash` would silently serve a cached method_id
    for the wrong Capability binding."""
    with TestClient(create_app()) as client:
        # Two distinct Method-shaped Capabilities for the collision test
        # — using create_capability_via_api directly so each call writes
        # a fresh Capability stream.
        cap_a = create_capability_via_api(client)
        cap_b = create_capability_via_api(client)

        headers = {"Idempotency-Key": "mk-cap-conflict"}
        r1 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "XRF Mapping",
                "needed_family_ids": [],
                "capability_id": cap_a,
            },
            headers=headers,
        )
        r2 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "XRF Mapping",
                "needed_family_ids": [],
                "capability_id": cap_b,
            },
            headers=headers,
        )

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_methods_same_key_reordered_capabilities_returns_same_method_id() -> None:
    """Frozenset semantics: needed_family_ids is set-equal regardless
    of input order. The cross-BC `_normalize_for_hash` helper sorts
    frozensets before SHA256 hashing (locked in Trust 3c) so reordered
    input is treated as the same logical body. Pinned end-to-end."""
    cap1 = str(uuid4())
    cap2 = str(uuid4())
    cap3 = str(uuid4())
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        headers = {"Idempotency-Key": "mk-3"}
        r1 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "X",
                "capability_id": _cap_id,
                "needed_family_ids": [cap1, cap2, cap3],
            },
            headers=headers,
        )
        r2 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "X",
                "capability_id": _cap_id,
                "needed_family_ids": [cap3, cap1, cap2],
            },
            headers=headers,
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["method_id"] == r2.json()["method_id"]


@pytest.mark.contract
def test_post_methods_different_keys_create_distinct_methods() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        r1 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "X",
                "capability_id": _cap_id,
                "needed_family_ids": [],
            },
            headers={"Idempotency-Key": "mk-A"},
        )
        r2 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "X",
                "capability_id": _cap_id,
                "needed_family_ids": [],
            },
            headers={"Idempotency-Key": "mk-B"},
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["method_id"] != r2.json()["method_id"]


@pytest.mark.contract
def test_post_methods_cached_response_returns_valid_uuid() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        headers = {"Idempotency-Key": "mk-uuid"}
        r1 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "X",
                "capability_id": _cap_id,
                "needed_family_ids": [],
            },
            headers=headers,
        )
        r2 = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "X",
                "capability_id": _cap_id,
                "needed_family_ids": [],
            },
            headers=headers,
        )

    UUID(r1.json()["method_id"])  # parses
    UUID(r2.json()["method_id"])  # parses
    assert r1.json()["method_id"] == r2.json()["method_id"]
