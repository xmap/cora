"""Contract tests for `Idempotency-Key` support on `POST /runs`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. Run is the 11th idempotency-wrapped create-style command.
Test keys are short to stay below the gitleaks generic-API-key
entropy threshold.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset


def _setup_chain(client: TestClient) -> tuple[str, str]:
    _cap_id = create_capability_via_api(client)
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "M",
            "capability_id": _cap_id,
            "needed_family_ids": [cap_id],
        },
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets", json={"name": "A", "tier": "Unit", "parent_id": None, "facility_code": "cora"}
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "test"}
    )
    return plan_id, subject_id


@pytest.mark.contract
def test_post_runs_without_key_creates_distinct_runs_on_each_call() -> None:
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_chain(client)
        body = {"name": "X", "plan_id": plan_id, "subject_id": subject_id}
        r1 = client.post("/runs", json=body)
        r2 = client.post("/runs", json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["run_id"] != r2.json()["run_id"]


@pytest.mark.contract
def test_post_runs_same_key_and_body_returns_same_run_id() -> None:
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_chain(client)
        body = {"name": "X", "plan_id": plan_id, "subject_id": subject_id}
        headers = {"Idempotency-Key": "rn-1"}
        r1 = client.post("/runs", json=body, headers=headers)
        r2 = client.post("/runs", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["run_id"] == r2.json()["run_id"]


@pytest.mark.contract
def test_post_runs_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_chain(client)
        headers = {"Idempotency-Key": "rn-2"}
        r1 = client.post(
            "/runs",
            json={"name": "X", "plan_id": plan_id, "subject_id": subject_id},
            headers=headers,
        )
        r2 = client.post(
            "/runs",
            json={"name": "Y", "plan_id": plan_id, "subject_id": subject_id},
            headers=headers,
        )

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_runs_different_keys_create_distinct_runs() -> None:
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_chain(client)
        body = {"name": "X", "plan_id": plan_id, "subject_id": subject_id}
        r1 = client.post("/runs", json=body, headers={"Idempotency-Key": "rn-A"})
        r2 = client.post("/runs", json=body, headers={"Idempotency-Key": "rn-B"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["run_id"] != r2.json()["run_id"]


@pytest.mark.contract
def test_post_runs_cached_response_returns_valid_uuid() -> None:
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_chain(client)
        body = {"name": "X", "plan_id": plan_id, "subject_id": subject_id}
        headers = {"Idempotency-Key": "rn-uuid"}
        r1 = client.post("/runs", json=body, headers=headers)
        r2 = client.post("/runs", json=body, headers=headers)

    UUID(r1.json()["run_id"])
    UUID(r2.json()["run_id"])
    assert r1.json()["run_id"] == r2.json()["run_id"]
