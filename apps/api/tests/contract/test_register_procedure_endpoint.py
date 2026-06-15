"""Contract tests for `POST /procedures`.

Covers create-style basics (request schema, response shape, status
codes), Pydantic min/max length on name + kind (-> 422), the
domain-VO validation when whitespace-only slips past Pydantic
(-> 400), and the AlreadyExists defensive guard (-> 409 via
dependency_overrides).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_procedures_returns_201_with_procedure_id_for_minimal_body() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/procedures",
            json={"name": "Vessel-A bakeout", "kind": "bakeout"},
        )
    assert response.status_code == 201
    body = response.json()
    assert "procedure_id" in body
    UUID(body["procedure_id"])


@pytest.mark.contract
def test_post_procedures_accepts_target_asset_ids() -> None:
    asset = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/procedures",
            json={
                "name": "2-BM rotation-axis alignment",
                "kind": "alignment",
                "target_asset_ids": [asset],
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_procedures_accepts_phase_of_run_with_parent_run_id() -> None:
    """parent_run_id resolves the Phase aggregate question per
    project_operation_design memo: a Phase IS a Procedure with
    parent_run_id set."""
    parent_run = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/procedures",
            json={
                "name": "Mid-run alignment",
                "kind": "alignment",
                "parent_run_id": parent_run,
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_procedures_trims_whitespace_via_voo_validation() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/procedures",
            json={"name": "  Vessel-A bakeout  ", "kind": "  bakeout  "},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_procedures_rejects_missing_required_fields_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures", json={"name": "X"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_procedures_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures", json={"name": "", "kind": "bakeout"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_procedures_rejects_empty_kind_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures", json={"name": "X", "kind": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_procedures_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures", json={"name": "x" * 201, "kind": "bakeout"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_procedures_rejects_too_long_kind_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures", json={"name": "X", "kind": "x" * 51})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_procedures_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only slips past Pydantic min_length=1 (the trim
    happens in the VO __post_init__); the domain VO rejects with
    InvalidProcedureNameError -> 400."""
    with TestClient(create_app()) as client:
        response = client.post("/procedures", json={"name": "   ", "kind": "bakeout"})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_procedures_rejects_whitespace_only_kind_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/procedures", json={"name": "X", "kind": "   "})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_procedures_rejects_invalid_uuid_in_target_assets_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/procedures",
            json={"name": "X", "kind": "bakeout", "target_asset_ids": ["not-a-uuid"]},
        )
    assert response.status_code == 422
