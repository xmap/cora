"""Contract tests for `Idempotency-Key` support on `POST /plans`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. Plan is the 10th idempotency-wrapped create-style command.
Test keys are short to stay below the gitleaks generic-API-key
entropy threshold.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import seed_method_chain


def _setup_chain(client: TestClient) -> tuple[str, str]:
    """Plan-idempotency tests POST `/plans` themselves to exercise the
    idempotency wrap, so the helper stops one step short of Plan."""
    chain = seed_method_chain(client)
    return chain.practice_id, chain.asset_id


@pytest.mark.contract
def test_post_plans_without_key_creates_distinct_plans_on_each_call() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id = _setup_chain(client)
        body = {"name": "X", "practice_id": practice_id, "asset_ids": [asset_id]}
        r1 = client.post("/plans", json=body)
        r2 = client.post("/plans", json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["plan_id"] != r2.json()["plan_id"]


@pytest.mark.contract
def test_post_plans_same_key_and_body_returns_same_plan_id() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id = _setup_chain(client)
        body = {"name": "X", "practice_id": practice_id, "asset_ids": [asset_id]}
        headers = {"Idempotency-Key": "pl-1"}
        r1 = client.post("/plans", json=body, headers=headers)
        r2 = client.post("/plans", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["plan_id"] == r2.json()["plan_id"]


@pytest.mark.contract
def test_post_plans_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id = _setup_chain(client)
        headers = {"Idempotency-Key": "pl-2"}
        r1 = client.post(
            "/plans",
            json={"name": "X", "practice_id": practice_id, "asset_ids": [asset_id]},
            headers=headers,
        )
        r2 = client.post(
            "/plans",
            json={"name": "Y", "practice_id": practice_id, "asset_ids": [asset_id]},
            headers=headers,
        )

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_plans_different_keys_create_distinct_plans() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id = _setup_chain(client)
        body = {"name": "X", "practice_id": practice_id, "asset_ids": [asset_id]}
        r1 = client.post("/plans", json=body, headers={"Idempotency-Key": "pl-A"})
        r2 = client.post("/plans", json=body, headers={"Idempotency-Key": "pl-B"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["plan_id"] != r2.json()["plan_id"]


@pytest.mark.contract
def test_post_plans_same_key_with_reordered_asset_ids_returns_same_plan_id() -> None:
    """asset_ids is a set semantically; the canonical-bytes hashing
    via _normalize_for_hash (Trust 3c) sorts before hashing so
    different iteration orders of the same logical set hit the
    cached entry."""
    with TestClient(create_app()) as client:
        practice_id, asset_id_1 = _setup_chain(client)
        # Add a second asset with the same capability.
        cap_id = client.post("/families", json={"name": "OtherCap", "affordances": []}).json()[
            "family_id"
        ]
        # Add OtherCap to first asset.
        client.post(f"/assets/{asset_id_1}/add-family", json={"family_id": cap_id})
        asset_id_2 = client.post(
            "/assets",
            json={"name": "Asset2", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
        ).json()["asset_id"]
        # asset_id_2 doesn't need any capability beyond what's already
        # required (the single FlyMotion). Add it.
        first_cap_id = client.post(
            f"/assets/{asset_id_2}/add-family",
            json={"family_id": cap_id},
        )
        # Skip the asset_id_2 capability check; for this test we just
        # need both to satisfy the Method's needs (which is single
        # capability "FlyMotion"). asset_id_1 already has it.
        _ = first_cap_id

        headers = {"Idempotency-Key": "pl-reord"}
        r1 = client.post(
            "/plans",
            json={
                "name": "X",
                "practice_id": practice_id,
                "asset_ids": [asset_id_1, asset_id_2],
            },
            headers=headers,
        )
        r2 = client.post(
            "/plans",
            json={
                "name": "X",
                "practice_id": practice_id,
                "asset_ids": [asset_id_2, asset_id_1],
            },
            headers=headers,
        )

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["plan_id"] == r2.json()["plan_id"]


@pytest.mark.contract
def test_post_plans_cached_response_returns_valid_uuid() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id = _setup_chain(client)
        body = {"name": "X", "practice_id": practice_id, "asset_ids": [asset_id]}
        headers = {"Idempotency-Key": "pl-uuid"}
        r1 = client.post("/plans", json=body, headers=headers)
        r2 = client.post("/plans", json=body, headers=headers)

    UUID(r1.json()["plan_id"])
    UUID(r2.json()["plan_id"])
    assert r1.json()["plan_id"] == r2.json()["plan_id"]
