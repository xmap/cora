"""Contract tests for the cross-BC Enclosure pre-flight gate on POST /runs.

Pins the wire-level behavior of the gate added in Sub-Slice F:
  - 200 happy path (no Enclosure binds any Asset) -- Permit-by-default
    per L-pre-1; the test app's `AlwaysPermittedEnclosureLookup` stub
    naturally exercises this branch via `find_for_assets -> []`.
  - 200 happy path (an Active+Permitted Enclosure DOES bind an
    Asset) -- the gate accepts the row and start_run proceeds.
  - 409 NotPermitted: the Enclosure binding the Asset is in
    permit_status="NotPermitted" -> RunRequiresPermittedEnclosureError.
  - 409 Unknown: same shape with permit_status="Unknown".
  - 409 Decommissioned: the row reaching the decider has
    lifecycle="Decommissioned" -> defensive fail.

Swap-in pattern: tests that need a specific failing/passing row
replace `app.state.deps.enclosure_lookup` with a seeded
`InMemoryEnclosureLookup` AFTER `create_app()` runs (Kernel is frozen,
so we `dataclasses.replace(...)` it).
"""

import dataclasses
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.adapters.in_memory_enclosure_lookup import (
    InMemoryEnclosureLookup,
)
from cora.infrastructure.ports.enclosure_lookup import EnclosureReference
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset


def _setup_chain(client: TestClient) -> tuple[str, str, str]:
    """Build the Family + Asset + Method + Practice + Plan + Subject chain.

    Returns (plan_id, subject_id, asset_id). The asset_id is returned
    so the test can seed an EnclosureReference whose
    `containing_asset_id` matches.
    """
    _cap_id = create_capability_via_api(client)
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
        json={
            "name": "A",
            "tier": "Unit",
            "parent_id": None,
            "facility_code": "cora",
        },
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
    return plan_id, subject_id, asset_id


def _install_enclosure_lookup(app: FastAPI, lookup) -> None:  # type: ignore[no-untyped-def]
    """Swap the kernel's enclosure_lookup for a seeded in-memory adapter.

    Kernel is a frozen dataclass: rebuild it via `dataclasses.replace`
    and rebind `app.state.deps`. The wiring closures in `wire_run`
    already captured the OLD kernel, so we re-wire after the swap.
    """
    from cora.run import wire_run

    new_deps = dataclasses.replace(app.state.deps, enclosure_lookup=lookup)
    app.state.deps = new_deps
    app.state.run = wire_run(new_deps)


@pytest.mark.contract
def test_post_runs_returns_201_when_no_enclosure_binds_any_asset() -> None:
    """Permit-by-default happy path: the test app's default
    AlwaysPermittedEnclosureLookup stub returns [] from
    find_for_assets, so the gate trivially passes."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, _ = _setup_chain(client)
        response = client.post(
            "/runs",
            json={"name": "happy", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_runs_returns_201_when_binding_enclosure_is_permitted_and_active() -> None:
    """Active+Permitted binding: the gate accepts the row, start_run proceeds."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, asset_id = _setup_chain(client)
        lookup = InMemoryEnclosureLookup()
        lookup.register(
            enclosure_id=uuid4(),
            name="A-Hutch",
            containing_asset_id=UUID(asset_id),
            permit_status="Permitted",
            lifecycle="Active",
        )
        _install_enclosure_lookup(app, lookup)
        response = client.post(
            "/runs",
            json={"name": "happy-bound", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
@pytest.mark.parametrize("permit_status", ["NotPermitted", "Unknown"])
def test_post_runs_returns_409_when_binding_enclosure_is_not_permitted(
    permit_status: str,
) -> None:
    """A non-Permitted binding raises 409 RunRequiresPermittedEnclosureError."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, asset_id = _setup_chain(client)
        lookup = InMemoryEnclosureLookup()
        lookup.register(
            enclosure_id=uuid4(),
            name="A-Hutch",
            containing_asset_id=UUID(asset_id),
            permit_status=permit_status,
            lifecycle="Active",
        )
        _install_enclosure_lookup(app, lookup)
        response = client.post(
            "/runs",
            json={"name": "blocked", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "Enclosure" in detail
    assert "one or more referencing Enclosures" in detail


@pytest.mark.contract
def test_post_runs_returns_409_coverage_mismatch_for_mixed_permitted_and_not_permitted() -> None:
    """Mixed Permitted + NotPermitted bindings on the same Asset raise
    409 RunEnclosureCoverageMismatchError. Discriminating substring
    pins the CoverageMismatch branch versus the Requires branch."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, asset_id = _setup_chain(client)
        lookup = InMemoryEnclosureLookup()
        lookup.register(
            enclosure_id=uuid4(),
            name="A-Hutch-Pass",
            containing_asset_id=UUID(asset_id),
            permit_status="Permitted",
            lifecycle="Active",
        )
        lookup.register(
            enclosure_id=uuid4(),
            name="A-Hutch-Fail",
            containing_asset_id=UUID(asset_id),
            permit_status="NotPermitted",
            lifecycle="Active",
        )
        _install_enclosure_lookup(app, lookup)
        response = client.post(
            "/runs",
            json={"name": "mixed", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "Enclosure" in detail
    assert "failed the Permitted-and-Active gate" in detail


@pytest.mark.contract
def test_post_runs_returns_409_when_binding_enclosure_is_decommissioned() -> None:
    """A Decommissioned row reaching the decider fails defensively."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, asset_id = _setup_chain(client)
        lookup = InMemoryEnclosureLookup()
        lookup.register(
            enclosure_id=uuid4(),
            name="A-Hutch",
            containing_asset_id=UUID(asset_id),
            permit_status="Permitted",
            lifecycle="Decommissioned",
        )

        # The InMemoryEnclosureLookup.find_for_assets implementation
        # filters by lifecycle == "Active" (mirrors the production
        # adapter), so an injected Decommissioned row is naturally
        # excluded at the read layer. Patch the adapter directly to
        # return it anyway so the decider's defensive guard is the
        # path under test (the production adapter could be a future
        # different implementation that does not filter).
        class _AlwaysReturnLookup:
            async def lookup(self, enclosure_id):  # type: ignore[no-untyped-def]
                return None

            async def find_for_assets(
                self, *, asset_ids: frozenset[UUID]
            ) -> list[EnclosureReference]:
                del asset_ids
                return list(lookup._records.values())  # type: ignore[reportPrivateUsage]

        _install_enclosure_lookup(app, _AlwaysReturnLookup())  # type: ignore[arg-type]
        response = client.post(
            "/runs",
            json={"name": "tombstoned", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "Enclosure" in detail
    assert "one or more referencing Enclosures" in detail
