"""Contract tests for `GET /runs/{run_id}`.

Pinned response shape: `{id, name, plan_id, subject_id, status}`.
`subject_id` is null for calibration / dark-field runs.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset


def _setup_full_run(
    client: TestClient, *, with_subject: bool = True
) -> tuple[str, str, str | None]:
    _cap_id = create_capability_via_api(client)
    """Seed full upstream chain + start a Run. Returns (run_id, plan_id, subject_id)."""
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods", json={"name": "M", "capability_id": _cap_id, "needed_family_ids": [cap_id]}
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "A", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    subject_id: str | None = None
    if with_subject:
        subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
        mount_asset_id = register_active_asset(client)
        client.post(
            f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "test"}
        )
    body: dict[str, object] = {"name": "32-ID FlyScan", "plan_id": plan_id}
    if subject_id is not None:
        body["subject_id"] = subject_id
    run_id = client.post("/runs", json=body).json()["run_id"]
    return run_id, plan_id, subject_id


@pytest.mark.contract
def test_get_run_returns_200_with_running_status_for_sample_run() -> None:
    with TestClient(create_app()) as client:
        run_id, plan_id, subject_id = _setup_full_run(client, with_subject=True)
        response = client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": run_id,
        "name": "32-ID FlyScan",
        "plan_id": plan_id,
        "subject_id": subject_id,
        "raid": None,
        "status": "Running",
        # 6g-c additive response surface: empty defaults when no
        # overrides / no Plan defaults / no trigger_source were supplied.
        "override_parameters": {},
        "effective_parameters": {},
        "trigger_source": None,
        # 6i-c additive response surface (Watch #17): campaign_id is
        # None for standalone runs (no Campaign membership set at
        # start time or via add_run_to_campaign).
        "campaign_id": None,
    }


@pytest.mark.contract
def test_get_run_returns_null_subject_id_for_dark_field_run() -> None:
    """Calibration / dark-field runs serialize subject_id as JSON null."""
    with TestClient(create_app()) as client:
        run_id, _, _ = _setup_full_run(client, with_subject=False)
        response = client.get(f"/runs/{run_id}")

    body = response.json()
    assert body["subject_id"] is None


@pytest.mark.contract
def test_get_run_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/runs/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_run_returns_422_for_malformed_run_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/runs/not-a-uuid")
    assert response.status_code == 422
