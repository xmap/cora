"""Contract tests for the parameter surface on `POST /runs` and
`GET /runs/{id}`.

Exercises:
  - start_run accepts `override_parameters` + `trigger_source` body fields
  - effective_parameters = merge(plan.default_parameters, overrides)
  - get_run surfaces override_parameters + effective_parameters + trigger_source
  - Method-without-schema is STRICT: rejects non-empty effective_parameters
    with 400 + clear error message
  - Method-with-schema validates effective_parameters at start (400 on violation)
  - Plan defaults flow through when overrides omitted
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
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


def _setup_run_chain(
    client: TestClient,
    *,
    method_schema: dict[str, Any] | None = None,
    plan_defaults: dict[str, Any] | None = None,
) -> tuple[str, str]:
    _cap_id = create_capability_via_api(client)
    """Seed Family + Method (optionally with schema) + Practice +
    Asset + Plan (optionally with defaults) + Subject (Mounted).
    Returns (plan_id, subject_id)."""
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={"name": "Test Method", "capability_id": _cap_id, "needed_family_ids": [cap_id]},
    ).json()["method_id"]
    if method_schema is not None:
        r = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": method_schema},
        )
        assert r.status_code == 204, r.text
    practice_id = client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={
            "name": "TestAsset",
            "tier": "Unit",
            "parent_id": None,
            "facility_code": "cora",
        },
    ).json()["asset_id"]
    add_resp = client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    assert add_resp.status_code == 204
    plan_id = client.post(
        "/plans",
        json={"name": "32-ID FlyScan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    if plan_defaults:
        r2 = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={"default_parameters_patch": plan_defaults},
        )
        assert r2.status_code == 204, r2.text
    subject_id = client.post("/subjects", json={"name": "PorousCeramicSample-A"}).json()[
        "subject_id"
    ]
    mount_asset_id = register_active_asset(client)
    mount_resp = client.post(
        f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "test"}
    )
    assert mount_resp.status_code == 204
    return plan_id, subject_id


@pytest.mark.contract
def test_start_run_accepts_override_parameters_and_trigger_source() -> None:
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_run_chain(
            client, method_schema=_energy_schema(), plan_defaults={"energy": 12.0}
        )
        response = client.post(
            "/runs",
            json={
                "name": "Run-with-overrides",
                "plan_id": plan_id,
                "subject_id": subject_id,
                "override_parameters": {"exposure": 250},
                "trigger_source": "operator:opid:5",
            },
        )
    assert response.status_code == 201, response.text
    UUID(response.json()["run_id"])


@pytest.mark.contract
def test_get_run_surfaces_effective_parameters_after_merge() -> None:
    """effective_parameters in the response = Plan defaults merged
    with the operator's overrides at start time."""
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_run_chain(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 12.0, "exposure": 100},
        )
        post = client.post(
            "/runs",
            json={
                "name": "Run-X",
                "plan_id": plan_id,
                "subject_id": subject_id,
                "override_parameters": {"exposure": 250},
                "trigger_source": "operator:opid:5",
            },
        )
        assert post.status_code == 201, post.text
        run_id = post.json()["run_id"]

        get = client.get(f"/runs/{run_id}")
    assert get.status_code == 200
    body = get.json()
    assert body["override_parameters"] == {"exposure": 250}
    # Defaults' energy preserved + override's exposure wins.
    assert body["effective_parameters"] == {"energy": 12.0, "exposure": 250}
    assert body["trigger_source"] == "operator:opid:5"


@pytest.mark.contract
def test_start_run_returns_400_when_effective_parameters_violate_schema() -> None:
    """Operator override pushes the effective_parameters out of the
    Method's parameters_schema bounds -> 400."""
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_run_chain(
            client, method_schema=_energy_schema(), plan_defaults={"energy": 12.0}
        )
        response = client.post(
            "/runs",
            json={
                "name": "Run-bad",
                "plan_id": plan_id,
                "subject_id": subject_id,
                "override_parameters": {"energy": 1.0},
            },
        )
    assert response.status_code == 400, response.text
    body = response.json()
    assert "Invalid Run parameters" in body["detail"]


@pytest.mark.contract
def test_start_run_strict_when_method_has_no_schema() -> None:
    """Strict: Method without parameters_schema
    rejects non-empty effective_parameters with a clear 400. Operator's
    fix is to declare a schema (an empty `{}` works for parameter-less
    Methods) or omit overrides AND clear Plan defaults."""
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_run_chain(client, method_schema=None)
        response = client.post(
            "/runs",
            json={
                "name": "Run-strict",
                "plan_id": plan_id,
                "subject_id": subject_id,
                "override_parameters": {"undeclared": "anything"},
            },
        )
    assert response.status_code == 400, response.text
    body = response.json()
    assert "Method declares no parameters_schema" in body["detail"]


@pytest.mark.contract
def test_start_run_accepts_no_schema_when_no_overrides_and_no_defaults() -> None:
    """Strict still allows the trivial case: no Plan defaults, no
    overrides, no Method schema -> empty effective_parameters,
    accepted."""
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_run_chain(client, method_schema=None)
        response = client.post(
            "/runs",
            json={
                "name": "Run-empty-trivial",
                "plan_id": plan_id,
                "subject_id": subject_id,
            },
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_get_run_returns_plan_defaults_as_effective_when_no_overrides() -> None:
    """Operator omits override_parameters -> effective_parameters
    equals Plan.default_parameters straight."""
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_run_chain(
            client,
            method_schema=_energy_schema(),
            plan_defaults={"energy": 12.0, "exposure": 100},
        )
        post = client.post(
            "/runs",
            json={"name": "Run-defaults-only", "plan_id": plan_id, "subject_id": subject_id},
        )
        assert post.status_code == 201, post.text
        run_id = post.json()["run_id"]
        get = client.get(f"/runs/{run_id}")
    assert get.status_code == 200
    body = get.json()
    assert body["override_parameters"] == {}
    assert body["effective_parameters"] == {"energy": 12.0, "exposure": 100}
    assert body["trigger_source"] is None


@pytest.mark.contract
def test_start_run_defaults_to_empty_when_neither_plan_nor_overrides_set() -> None:
    """No Plan defaults, no overrides -> effective_parameters = {}."""
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_run_chain(client, method_schema=None)
        post = client.post(
            "/runs",
            json={"name": "Run-empty", "plan_id": plan_id, "subject_id": subject_id},
        )
        assert post.status_code == 201, post.text
        run_id = post.json()["run_id"]
        get = client.get(f"/runs/{run_id}")
    body = get.json()
    assert body["override_parameters"] == {}
    assert body["effective_parameters"] == {}
