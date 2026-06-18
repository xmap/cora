"""Shared test helpers for contract tests against the FastAPI app.

Every POST `/methods` body requires a `capability_id` referencing
a real Capability stream. Contract
tests use TestClient + a fresh app per test, so each test must
POST `/capabilities` first to create a Capability before POSTing
`/methods`. This helper hides the boilerplate:

    cap_id = create_capability_via_api(client)
    method_id = client.post(
        "/methods",
        json={"name": "M", "needed_family_ids": [], "capability_id": cap_id},
    ).json()["method_id"]

Each call creates a UNIQUE Capability code (uuid-suffixed) so
tests that issue many POSTs to /methods in the same TestClient
session don't collide on the Recipe Capability uniqueness
invariants (none today, but defensive).

## Upstream-chain seeders

`seed_method_chain` and `seed_run_upstream_chain` hoist the
copy-pasted setup sequences from `test_abort_run_endpoint`,
`test_adjust_run_idempotency`, and `test_define_plan_idempotency`.
They mirror the integration-tier `seed_run_upstream_chain_postgres` so
the contract and integration tiers tell the same story about what
"a Run needs upstream" — at the wire level via TestClient here,
against real PG there.
"""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.contract._subject_helpers import register_active_asset


def create_capability_via_api(
    client: TestClient,
    *,
    executor_shapes: list[str] | None = None,
    required_affordances: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    """POST a fresh Method-shaped Capability, return its UUID string.

    Defaults to `executor_shapes=["Method"]` (the Method-binding
    contract) + empty `required_affordances` (no affordance gating,
    so Plan binding never trips the 6l.B guard for these tests).
    Each call generates a unique `code` suffix so repeated calls
    within one test don't collide.

    `headers` forwards request headers (typically `X-Principal-Id`)
    so tests running under a non-default principal can still seed
    a Capability — the Trust authorize gate requires the principal
    to be in the policy permitted set for `DefineCapability`.
    """
    body: dict[str, Any] = {
        "code": f"cora.capability.contract.test.{uuid4().hex[:12]}",
        "name": "ContractTestCapability",
        "required_affordances": required_affordances or [],
        "executor_shapes": executor_shapes or ["Method"],
    }
    response = client.post("/capabilities", json=body, headers=headers or {})
    if response.status_code != 201:
        raise AssertionError(
            f"create_capability_via_api expected 201, got {response.status_code}: {response.text}"
        )
    return response.json()["capability_id"]


@dataclass(frozen=True)
class MethodChainIds:
    """Ids returned by `seed_method_chain`. Field names match the
    JSON keys the upstream endpoints respond with."""

    capability_id: str
    family_id: str
    method_id: str
    practice_id: str
    asset_id: str


def seed_method_chain(
    client: TestClient,
    *,
    parameters_schema: dict[str, Any] | None = None,
) -> MethodChainIds:
    """Seed Capability + Family + Method + Practice + Asset (with Family).

    The prefix every Run-shaped contract test shares. Pass
    `parameters_schema=` to additionally PATCH the Method's
    `parameters_schema` — required when the test later supplies
    `override_parameters` or `default_parameters_patch` per the
    5g-c STRICT-validation anchor.
    """
    capability_id = create_capability_via_api(client)
    family_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={
            "name": "M",
            "capability_id": capability_id,
            "execution_pattern": "Batch",
            "needed_family_ids": [family_id],
        },
    ).json()["method_id"]
    if parameters_schema is not None:
        r = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": parameters_schema},
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
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": family_id})
    return MethodChainIds(
        capability_id=capability_id,
        family_id=family_id,
        method_id=method_id,
        practice_id=practice_id,
        asset_id=asset_id,
    )


def seed_run_upstream_chain(
    client: TestClient,
    *,
    parameters_schema: dict[str, Any] | None = None,
    plan_defaults: dict[str, Any] | None = None,
    run_name: str = "32-ID FlyScan",
) -> str:
    """Seed the full upstream chain a Run needs and start it. Returns the run_id.

    Contract-tier sibling of `tests/integration/_helpers.seed_run_upstream_chain_postgres`.
    Builds on `seed_method_chain`, then defines a Plan (optionally with
    `default_parameters`), registers + mounts a Subject onto a fresh
    Active Asset, and POSTs `/runs` to start the Run.
    """
    chain = seed_method_chain(client, parameters_schema=parameters_schema)
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": chain.practice_id, "asset_ids": [chain.asset_id]},
    ).json()["plan_id"]
    if plan_defaults is not None:
        r = client.patch(
            f"/plans/{plan_id}/default-parameters",
            json={"default_parameters_patch": plan_defaults},
        )
        assert r.status_code == 204, r.text
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": mount_asset_id, "reason": "test"},
    )
    return client.post(
        "/runs",
        json={"name": run_name, "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]


__all__ = [
    "MethodChainIds",
    "create_capability_via_api",
    "seed_method_chain",
    "seed_run_upstream_chain",
]
