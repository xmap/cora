"""Contract tests for `PATCH /plans/{plan_id}/default-parameters`.

Action endpoint with body `{default_parameters_patch}`.
RFC 7396 merge semantics. Validates against the owning Method's
parameters_schema; STRICT when the Method declares no schema
(non-empty defaults rejected when no schema declared).
Mirrors `test_update_asset_settings_endpoint.py` shape.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _example_method_schema() -> dict[str, Any]:
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


def _setup_plan_with_schema(
    client: TestClient,
    *,
    method_schema: dict[str, Any] | None = None,
) -> str:
    _cap_id = create_capability_via_api(client)
    """Seed all upstream + a Plan; optionally set a Method
    parameters_schema. Returns plan_id (str)."""
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={"name": "Test Method", "capability_id": _cap_id, "needed_family_ids": [cap_id]},
    ).json()["method_id"]
    if method_schema is not None:
        resp = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": method_schema},
        )
        assert resp.status_code == 204, resp.text
    practice_id = client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "TestAsset", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    plan_id: str = client.post(
        "/plans",
        json={
            "name": "32-ID FlyScan",
            "practice_id": practice_id,
            "asset_ids": [asset_id],
        },
    ).json()["plan_id"]
    return plan_id


@pytest.mark.contract
def test_patch_plan_default_parameters_returns_204_when_setting_defaults() -> None:
    with TestClient(create_app()) as client:
        plan_id = _setup_plan_with_schema(client, method_schema=_example_method_schema())
        response = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={"default_parameters_patch": {"energy": 12.0}},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_patch_plan_default_parameters_returns_204_when_clearing_via_null() -> None:
    """RFC 7396 null-deletes-key semantics."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan_with_schema(client, method_schema=_example_method_schema())
        first = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={"default_parameters_patch": {"energy": 12.0}},
        )
        assert first.status_code == 204
        cleared = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={"default_parameters_patch": {"energy": None}},
        )
    assert cleared.status_code == 204


@pytest.mark.contract
def test_patch_plan_default_parameters_returns_400_for_constraint_violation() -> None:
    """Post-merge value below schema minimum -> 400."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan_with_schema(client, method_schema=_example_method_schema())
        response = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={"default_parameters_patch": {"energy": 1.0}},
        )
    assert response.status_code == 400
    body = response.json()
    assert "Invalid Plan default_parameters" in body["detail"]


@pytest.mark.contract
def test_patch_plan_default_parameters_strict_when_method_has_no_schema() -> None:
    """Strict: Method without parameters_schema
    rejects non-empty defaults with a clear 400. Operator's fix is to
    declare a schema on the Method (an empty `{}` works for parameter-
    less Methods) or omit defaults."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan_with_schema(client, method_schema=None)
        response = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={"default_parameters_patch": {"undeclared_key": "anything"}},
        )
    assert response.status_code == 400
    body = response.json()
    assert "Method declares no parameters_schema" in body["detail"]


@pytest.mark.contract
def test_patch_plan_default_parameters_accepts_empty_when_method_has_no_schema() -> None:
    """Strict still allows the trivial 'no contract + no values'
    state: clearing all defaults on a no-schema Method works."""
    with TestClient(create_app()) as client:
        plan_id = _setup_plan_with_schema(client, method_schema=None)
        response = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={"default_parameters_patch": {}},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_patch_plan_default_parameters_returns_404_for_unknown_plan() -> None:
    unknown_id = uuid4()
    with TestClient(create_app()) as client:
        response = client.patch(
            f"/plans/{unknown_id}/default-parameters",
            json={"default_parameters_patch": {"energy": 12.0}},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_patch_plan_default_parameters_returns_422_for_malformed_path() -> None:
    """Bad UUID in path -> Pydantic 422."""
    with TestClient(create_app()) as client:
        response = client.patch(
            "/plans/not-a-uuid/default-parameters",
            json={"default_parameters_patch": {}},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_patch_plan_default_parameters_returns_422_for_missing_body_field() -> None:
    """Body must include the default_parameters_patch field."""
    plan_id = str(UUID(int=1))
    with TestClient(create_app()) as client:
        response = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={},
        )
    assert response.status_code == 422
