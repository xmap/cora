"""Shared setup for compute-conduct contract tests (REST + MCP).

`setup_run_with_launch_spec` seeds a full Run whose Method carries a
vetted launch_spec, so both the REST and MCP conduct contract tests can
drive the server-side argv build from one source of truth.
"""

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def setup_run_with_launch_spec(client: TestClient) -> str:
    """Seed a Run whose Method carries a vetted launch_spec. Returns run_id.

    The Method has a parameters_schema (num_iter + remove_stripe) and a
    launch_spec binding those keys; the Run's override_parameters supply
    the values the server renders into argv.
    """
    capability_id = create_capability_via_api(client)
    family_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "recon",
            "capability_id": capability_id,
            "needed_family_ids": [family_id],
        },
    ).json()["method_id"]
    schema: dict[str, Any] = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "num_iter": {"type": "integer", "minimum": 1},
            "remove_stripe": {"type": "boolean"},
        },
    }
    assert (
        client.post(f"/methods/{method_id}/parameters-schema", json={"parameters_schema": schema})
    ).status_code == 204
    launch_spec = {
        "base_command": ["tomopy", "recon"],
        "args": [
            {"name": "num_iter", "flag": "--num-iter", "required": True},
            {"name": "remove_stripe", "flag": "--remove-stripe", "style": "flag_only"},
        ],
        "input_arg": "--input",
        "output_arg": "--output",
    }
    assert (
        client.post(f"/methods/{method_id}/launch-spec", json={"launch_spec": launch_spec})
    ).status_code == 204
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "A", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": family_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "x"})
    return client.post(
        "/runs",
        json={
            "name": "recon",
            "plan_id": plan_id,
            "subject_id": subject_id,
            "override_parameters": {"num_iter": 200, "remove_stripe": True},
        },
    ).json()["run_id"]
