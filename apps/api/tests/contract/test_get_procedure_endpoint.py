"""Contract tests for `GET /procedures/{procedure_id}`.

Mirrors `test_get_supply_endpoint.py` shape. Pinned response shape:
`{id, name, kind, target_asset_ids, status, parent_run_id}`.
target_asset_ids is a sorted list of UUIDs (deterministic ordering).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_procedure(
    client: TestClient,
    *,
    name: str = "Vessel-A bakeout",
    kind: str = "bakeout",
    target_asset_ids: list[str] | None = None,
    parent_run_id: str | None = None,
) -> UUID:
    body: dict[str, Any] = {"name": name, "kind": kind}
    if target_asset_ids is not None:
        body["target_asset_ids"] = target_asset_ids
    if parent_run_id is not None:
        body["parent_run_id"] = parent_run_id
    response = client.post("/procedures", json=body)
    assert response.status_code == 201, response.text
    return UUID(response.json()["procedure_id"])


@pytest.mark.contract
def test_get_procedure_returns_200_with_defined_status_for_new_procedure() -> None:
    asset1 = str(uuid4())
    asset2 = str(uuid4())
    with TestClient(create_app()) as client:
        procedure_id = _register_procedure(
            client,
            name="2-BM rotation-axis alignment",
            kind="alignment",
            target_asset_ids=[asset1, asset2],
        )
        response = client.get(f"/procedures/{procedure_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(procedure_id)
    assert body["name"] == "2-BM rotation-axis alignment"
    assert body["kind"] == "alignment"
    assert body["status"] == "Defined"
    # Sorted by UUID string form (deterministic).
    assert body["target_asset_ids"] == sorted([asset1, asset2])
    assert body["parent_run_id"] is None


@pytest.mark.contract
def test_get_procedure_returns_empty_target_asset_ids_for_facility_envelope() -> None:
    """Facility-envelope procedures (beam-mode change) act on no
    specific Asset; target_asset_ids returns [] in that case."""
    with TestClient(create_app()) as client:
        procedure_id = _register_procedure(client, name="Beam-mode change", kind="beam_mode_change")
        response = client.get(f"/procedures/{procedure_id}")

    assert response.status_code == 200
    assert response.json()["target_asset_ids"] == []


@pytest.mark.contract
def test_get_procedure_returns_parent_run_id_for_phase_of_run() -> None:
    parent_run = str(uuid4())
    with TestClient(create_app()) as client:
        procedure_id = _register_procedure(
            client,
            name="Mid-run alignment",
            kind="alignment",
            parent_run_id=parent_run,
        )
        response = client.get(f"/procedures/{procedure_id}")

    assert response.status_code == 200
    assert response.json()["parent_run_id"] == parent_run


@pytest.mark.contract
def test_get_procedure_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/procedures/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_procedure_returns_422_for_malformed_procedure_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/procedures/not-a-uuid")
    assert response.status_code == 422
