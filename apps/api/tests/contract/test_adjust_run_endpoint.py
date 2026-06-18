"""Contract tests for `POST /runs/{run_id}/adjust`.

Multi-source mid-flight steering: `Running | Held -> Running | Held`
(status preserved). Body carries `parameters_patch` (RFC 7396 merge
patch), `reason` (1-500 chars), optional `decided_by_decision_id`.
Returns 204 on success. Adjust on terminal Runs raises 409.
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _energy_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            },
            "exposure": {
                "type": "integer",
                "minimum": 1,
                "unit": {"system": "udunits", "code": "ms"},
            },
        },
    }


def _setup_full_run(
    client: TestClient,
    *,
    method_schema: dict[str, Any] | None = None,
    plan_defaults: dict[str, Any] | None = None,
) -> str:
    _cap_id = create_capability_via_api(client)
    """Seed full upstream chain + start a Run. Returns the run_id."""
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
    if method_schema is not None:
        r = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": method_schema},
        )
        assert r.status_code == 204, r.text
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
    if plan_defaults:
        r2 = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={"default_parameters_patch": plan_defaults},
        )
        assert r2.status_code == 204, r2.text
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": mount_asset_id, "reason": "test"},
    )
    run_id = client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]
    return run_id


@pytest.mark.contract
def test_post_adjust_run_returns_204_happy_path() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={
                "parameters_patch": {"energy": 12.0},
                "reason": "re-center on ROI",
            },
        )
    assert response.status_code == 204, response.text


def _load_adjusted_payload(app: FastAPI, run_id: UUID) -> dict[str, object]:
    """Load the last RunAdjusted payload directly from the event store.

    Mirrors the `_load_run_payload` helper in test_start_run_endpoint.py:
    when the response is 204 (no body), we drop down to the event store
    to verify the persisted event carries the expected payload field.
    """
    events, _ = asyncio.run(app.state.deps.event_store.load("Run", run_id))
    assert events, "expected at least one Run event"
    adjusted = [e for e in events if e.event_type == "RunAdjusted"]
    assert adjusted, "expected at least one RunAdjusted event"
    return dict(adjusted[-1].payload)


@pytest.mark.contract
def test_post_adjust_run_persists_decision_id_link_on_event() -> None:
    """Optional decided_by_decision_id flows through on the persisted
    event payload (no existence check at the write path). Drops down
    to the event store because the 204 response carries no body."""
    decision_id = uuid4()
    app = create_app()
    with TestClient(app) as client:
        run_id_str = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        response = client.post(
            f"/runs/{run_id_str}/adjust",
            json={
                "parameters_patch": {"energy": 13.0},
                "reason": "agent steering",
                "decided_by_decision_id": str(decision_id),
            },
        )
        assert response.status_code == 204, response.text

        payload = _load_adjusted_payload(app, UUID(run_id_str))
        assert payload["decided_by_decision_id"] == str(decision_id)
        assert payload["parameters_patch"] == {"energy": 13.0}


@pytest.mark.contract
def test_post_adjust_run_returns_204_from_held_state() -> None:
    """Multi-source guard accepts Held."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        client.post(f"/runs/{run_id}/hold")
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={
                "parameters_patch": {"energy": 14.0},
                "reason": "tune during pause",
            },
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_adjust_run_returns_404_when_run_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/runs/{missing_id}/adjust",
            json={"parameters_patch": {"x": 1}, "reason": "x"},
        )
    assert response.status_code == 404


@pytest.mark.contract
@pytest.mark.parametrize(
    ("transition", "expected_status"),
    [
        ("complete", "Completed"),
        ("abort", "Aborted"),
        ("stop", "Stopped"),
        ("truncate", "Truncated"),
    ],
)
def test_post_adjust_run_returns_409_for_each_terminal_state(
    transition: str, expected_status: str
) -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        if transition == "complete":
            client.post(f"/runs/{run_id}/complete")
        else:
            client.post(f"/runs/{run_id}/{transition}", json={"reason": "test"})

        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameters_patch": {"energy": 12.0}, "reason": "late adjust"},
        )
    assert response.status_code == 409, response.text
    assert expected_status in response.json()["detail"]


@pytest.mark.contract
def test_post_adjust_run_returns_400_for_empty_patch() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameters_patch": {}, "reason": "x"},
        )
    assert response.status_code == 400, response.text
    assert "at least one change" in response.json()["detail"]


@pytest.mark.contract
def test_post_adjust_run_returns_400_for_whitespace_only_reason() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameters_patch": {"energy": 12.0}, "reason": "   "},
        )
    assert response.status_code == 400, response.text
    assert "adjust reason" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_adjust_run_returns_400_when_merged_violates_schema() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={
                "parameters_patch": {"energy": 1.0},  # below minimum=5
                "reason": "x",
            },
        )
    assert response.status_code == 400, response.text
    assert "adjust" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_adjust_run_returns_422_when_reason_missing() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameters_patch": {"energy": 12.0}},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_adjust_run_returns_422_when_patch_missing() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"reason": "x"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_adjust_run_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/runs/not-a-uuid/adjust",
            json={"parameters_patch": {"x": 1}, "reason": "x"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_adjust_run_returns_422_for_bad_decision_id_uuid() -> None:
    """Body decided_by_decision_id must be a valid UUID (Pydantic
    boundary check; reaches FastAPI's 422 validator)."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={
                "parameters_patch": {"energy": 12.0},
                "reason": "x",
                "decided_by_decision_id": "not-a-uuid",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_adjust_run_returns_422_for_null_parameters_patch() -> None:
    """`parameters_patch` must be a dict (Pydantic boundary). null body
    field surfaces as 422 before the decider's emptiness check."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameters_patch": None, "reason": "x"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_adjust_run_returns_422_for_reason_over_max_length() -> None:
    """Reason is Field(max_length=500) at the API boundary; over-limit
    bodies surface as 422 before the decider's defensive 1-500 gate."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 10.0},
        )
        response = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameters_patch": {"energy": 12.0}, "reason": "x" * 501},
        )
    assert response.status_code == 422
