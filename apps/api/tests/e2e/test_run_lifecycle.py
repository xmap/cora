"""E2E smoke: full Run cascade from Family to Completed.

Keystone e2e: register every upstream aggregate (Family + Asset
+ Method + Practice + Plan + Subject + mount-target Asset + an
Active Safety Clearance bound to the Plan asset), start a Run
against the chain, complete it, then assert the Completed Run
appears in the projection-backed list endpoint.

Run-start is gated on at least one Active Safety Clearance
(`RunRequiresActiveClearanceError`); the production
`ClearanceLookup` wired here (not `AlwaysCoveredClearanceLookup`)
returns only what's actually been registered in the local DB, so
this test walks the 6-step Clearance lifecycle (Defined -> Submitted
-> UnderReview -> +ReviewStep[Approved] -> Approved -> Active) before
starting the Run.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from cora.safety.aggregates.clearance_template import clearance_template_stream_id


async def _register_and_activate_clearance(
    client: AsyncClient,
    *,
    facility_code: str,
    bound_asset_id: UUID,
) -> UUID:
    """Walk the 6-step Clearance lifecycle so the Run-start safety gate passes.

    `bound_asset_id` is the Asset id the Clearance gates against (matches
    `ClearanceLookup.find_covering`'s `asset_ids` set). Returns the
    activated Clearance's id."""
    template_id = clearance_template_stream_id(facility_code, "ESAF")
    registered = await client.post(
        "/clearances",
        json={
            "template_id": str(template_id),
            "facility_code": facility_code,
            "title": "E2E test clearance",
            "bindings": [{"kind": "Asset", "id": str(bound_asset_id)}],
        },
    )
    assert registered.status_code == 201, registered.text
    clearance_id = UUID(registered.json()["clearance_id"])

    submitted = await client.post(f"/clearances/{clearance_id}/submit")
    assert submitted.status_code == 204, submitted.text

    started = await client.post(
        f"/clearances/{clearance_id}/start-review",
        json={"first_reviewer_role": "BeamlineScientist"},
    )
    assert started.status_code == 204, started.text

    appended = await client.post(
        f"/clearances/{clearance_id}/review-steps",
        json={
            "step_index": 0,
            "role": "BeamlineScientist",
            "decision": "Approved",
            "decided_at": datetime.now(UTC).isoformat(),
        },
    )
    assert appended.status_code == 204, appended.text

    approved = await client.post(f"/clearances/{clearance_id}/approve", json={})
    assert approved.status_code == 204, approved.text

    activated = await client.post(f"/clearances/{clearance_id}/activate")
    assert activated.status_code == 204, activated.text

    return clearance_id


@pytest.mark.e2e
async def test_full_run_cascade_to_completed(
    e2e_client: AsyncClient,
    e2e_drain: Callable[[], Awaitable[None]],
) -> None:
    cap = await e2e_client.post("/families", json={"name": "FlyMotion", "affordances": []})
    family_id = cap.json()["family_id"]

    cap_template = await e2e_client.post(
        "/capabilities",
        json={
            "code": "cora.capability.e2e.run_lifecycle",
            "name": "E2ERunLifecycle",
            "required_affordances": [],
            "executor_shapes": ["Method"],
        },
    )
    capability_id = cap_template.json()["capability_id"]

    method = await e2e_client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "Test Method",
            "capability_id": capability_id,
            "needed_family_ids": [family_id],
        },
    )
    method_id = method.json()["method_id"]

    practice = await e2e_client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    )
    practice_id = practice.json()["practice_id"]

    plan_asset = await e2e_client.post(
        "/assets",
        json={"name": "PlanAsset", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    )
    plan_asset_id = plan_asset.json()["asset_id"]
    add = await e2e_client.post(
        f"/assets/{plan_asset_id}/add-family",
        json={"family_id": family_id},
    )
    assert add.status_code == 204

    plan = await e2e_client.post(
        "/plans",
        json={"name": "32-ID FlyScan", "practice_id": practice_id, "asset_ids": [plan_asset_id]},
    )
    plan_id = plan.json()["plan_id"]

    mount_asset = await e2e_client.post(
        "/assets",
        json={"name": "Goniometer-1", "tier": "Unit", "parent_id": str(uuid4())},
    )
    mount_asset_id = mount_asset.json()["asset_id"]
    activated = await e2e_client.post(f"/assets/{mount_asset_id}/activate")
    assert activated.status_code == 204

    subject = await e2e_client.post("/subjects", json={"name": "Sample-A1"})
    subject_id = subject.json()["subject_id"]
    mounted = await e2e_client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": mount_asset_id, "reason": "test"},
    )
    assert mounted.status_code == 204

    # the Plan asset so the Run-start safety lookup finds an Active
    # clearance covering the Run's scope. The lookup is projection-backed
    # (`proj_safety_clearance_summary`), so drain before starting the Run.
    await _register_and_activate_clearance(
        e2e_client,
        facility_code="cora",
        bound_asset_id=UUID(plan_asset_id),
    )
    await e2e_drain()

    started = await e2e_client.post(
        "/runs",
        json={"name": "Run-1", "plan_id": plan_id, "subject_id": subject_id},
    )
    assert started.status_code == 201, started.text
    run_id = UUID(started.json()["run_id"])

    completed = await e2e_client.post(f"/runs/{run_id}/complete")
    assert completed.status_code == 204

    await e2e_drain()
    listed = await e2e_client.get("/runs")
    assert listed.status_code == 200
    items = listed.json()["items"]
    matches = [item for item in items if item["run_id"] == str(run_id)]
    assert len(matches) == 1
    assert matches[0]["status"] == "Completed"
