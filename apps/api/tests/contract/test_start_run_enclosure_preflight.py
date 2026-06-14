"""Contract tests for the cross-BC Enclosure pre-flight gate on POST /runs.

Pins the wire-level behavior of the located-in Enclosure gate:
  - 201 happy path (no Asset in scope is located in any Enclosure) --
    Permit-by-default per L-pre-1; the test app's empty default
    asset_lookup carries no `located_in_enclosure_id`, so the gate's
    id-set is empty and it trivially passes.
  - 201 happy path (the Plan-bound Asset is located in an
    Active+Permitted Enclosure) -- the gate accepts the row and
    start_run proceeds.
  - 409 NotPermitted: the Enclosure the Asset is located in is in
    permit_status="NotPermitted" -> RunRequiresPermittedEnclosureError.
  - 409 Unknown: same shape with permit_status="Unknown".
  - 409 Decommissioned: the row reaching the decider has
    lifecycle="Decommissioned" -> defensive fail.

The new mental model: an Asset declares the Enclosure it sits in via
`located_in_enclosure_id`, surfaced on the AssetLookup projection row.
The run handler walks the Asset ancestor closure (`ancestors_of`),
collects each row's `located_in_enclosure_id`, and fetches those
Enclosures by id (`find_by_ids`). A Device inherits the located-in
Enclosure of a parent Unit/Component. Tests seed the
`InMemoryAssetLookup` with the located-in pointer (the test app's
default asset_lookup is empty) and the `InMemoryEnclosureLookup` with
the matching enclosure row.

Swap-in pattern: tests replace `app.state.deps.asset_lookup` and
`app.state.deps.enclosure_lookup` with seeded in-memory adapters AFTER
`create_app()` runs (Kernel is frozen, so we `dataclasses.replace(...)`
it and re-wire).
"""

import dataclasses
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.adapters.in_memory_asset_lookup import (
    InMemoryAssetLookup,
)
from cora.infrastructure.adapters.in_memory_enclosure_lookup import (
    InMemoryEnclosureLookup,
)
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset


def _setup_chain(client: TestClient) -> tuple[str, str, str]:
    """Build the Family + Asset + Method + Practice + Plan + Subject chain.

    Returns (plan_id, subject_id, asset_id). The asset_id is returned so
    the test can seed an AssetLookup row whose `located_in_enclosure_id`
    points at the Enclosure under test.
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


def _install_lookups(app: FastAPI, *, asset_lookup=None, enclosure_lookup=None) -> None:  # type: ignore[no-untyped-def]
    """Swap asset_lookup and/or enclosure_lookup in one replace + rewire.

    Kernel is a frozen dataclass: rebuild it via `dataclasses.replace`
    and rebind `app.state.deps`. The wiring closures in `wire_run`
    already captured the OLD kernel, so we re-wire after the swap.
    """
    from cora.run import wire_run

    changes: dict[str, object] = {}
    if asset_lookup is not None:
        changes["asset_lookup"] = asset_lookup
    if enclosure_lookup is not None:
        changes["enclosure_lookup"] = enclosure_lookup
    new_deps = dataclasses.replace(app.state.deps, **changes)
    app.state.deps = new_deps
    app.state.run = wire_run(new_deps)


def _seed_located_in_asset_lookup(asset_id: str, enclosure_id: UUID) -> InMemoryAssetLookup:
    """Seed an AssetLookup so the Plan-bound Asset is located in `enclosure_id`.

    The test app's asset_lookup is empty by default, so the located-in
    pointer the gate reads must be seeded here -- in production the same
    field lives in proj_equipment_asset_summary. The Asset is registered
    as a root Unit (no parent) carrying the located-in pointer directly.
    """
    lookup = InMemoryAssetLookup()
    lookup.register(
        UUID(asset_id),
        name="beamline-unit",
        tier="Unit",
        parent_id=None,
        located_in_enclosure_id=enclosure_id,
    )
    return lookup


@pytest.mark.contract
def test_post_runs_returns_201_when_no_enclosure_binds_any_asset() -> None:
    """Permit-by-default happy path: the test app's empty default
    asset_lookup carries no located_in_enclosure_id, so the gate's
    id-set is empty and it trivially passes."""
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
    """Active+Permitted located-in Enclosure: the gate accepts the row,
    start_run proceeds."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, asset_id = _setup_chain(client)
        enclosure_id = uuid4()
        enclosure_lookup = InMemoryEnclosureLookup()
        enclosure_lookup.register(
            enclosure_id=enclosure_id,
            name="A-Hutch",
            permit_status="Permitted",
            lifecycle="Active",
        )
        asset_lookup = _seed_located_in_asset_lookup(asset_id, enclosure_id)
        _install_lookups(app, asset_lookup=asset_lookup, enclosure_lookup=enclosure_lookup)
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
    """A non-Permitted located-in Enclosure raises 409
    RunRequiresPermittedEnclosureError."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, asset_id = _setup_chain(client)
        enclosure_id = uuid4()
        enclosure_lookup = InMemoryEnclosureLookup()
        enclosure_lookup.register(
            enclosure_id=enclosure_id,
            name="A-Hutch",
            permit_status=permit_status,
            lifecycle="Active",
        )
        asset_lookup = _seed_located_in_asset_lookup(asset_id, enclosure_id)
        _install_lookups(app, asset_lookup=asset_lookup, enclosure_lookup=enclosure_lookup)
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
    """A Device and a Unit ancestor located in two different Enclosures, one
    Permitted and one NotPermitted, raise 409 RunEnclosureCoverageMismatchError.
    Discriminating substring pins the CoverageMismatch branch versus the
    Requires branch."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, asset_id = _setup_chain(client)
        pass_enclosure_id = uuid4()
        fail_enclosure_id = uuid4()
        enclosure_lookup = InMemoryEnclosureLookup()
        enclosure_lookup.register(
            enclosure_id=pass_enclosure_id,
            name="A-Hutch-Pass",
            permit_status="Permitted",
            lifecycle="Active",
        )
        enclosure_lookup.register(
            enclosure_id=fail_enclosure_id,
            name="A-Hutch-Fail",
            permit_status="NotPermitted",
            lifecycle="Active",
        )
        # The Plan-bound Device sits in the Permitted Enclosure; its Unit
        # ancestor sits in the NotPermitted Enclosure. The walk collects
        # both located-in pointers, so the gate sees one passing and one
        # failing -> CoverageMismatch.
        parent_id = uuid4()
        asset_lookup = InMemoryAssetLookup()
        asset_lookup.register(
            UUID(asset_id),
            name="child-device",
            tier="Device",
            parent_id=parent_id,
            located_in_enclosure_id=pass_enclosure_id,
        )
        asset_lookup.register(
            parent_id,
            name="beamline-unit",
            tier="Unit",
            parent_id=None,
            located_in_enclosure_id=fail_enclosure_id,
        )
        _install_lookups(app, asset_lookup=asset_lookup, enclosure_lookup=enclosure_lookup)
        response = client.post(
            "/runs",
            json={"name": "mixed", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "Enclosure" in detail
    assert "failed the Permitted-and-Active gate" in detail


def _seed_child_parent_asset_lookup(asset_id: str, enclosure_id: UUID) -> InMemoryAssetLookup:
    """Seed an AssetLookup with `asset_id` as a Device under a Unit parent.

    The Unit parent carries the located-in pointer; the child Device has
    none of its own and inherits the parent's via the ancestor walk.
    Returns the lookup. The test app's asset_lookup is empty by default,
    so the walk needs this seed to have a chain to climb -- in production
    the same edges live in proj_equipment_asset_summary.
    """
    parent_id = uuid4()
    lookup = InMemoryAssetLookup()
    lookup.register(UUID(asset_id), name="child-device", tier="Device", parent_id=parent_id)
    lookup.register(
        parent_id,
        name="beamline-unit",
        tier="Unit",
        parent_id=None,
        located_in_enclosure_id=enclosure_id,
    )
    return lookup


@pytest.mark.contract
def test_post_runs_returns_409_when_ancestor_enclosure_is_not_permitted() -> None:
    """Inheritance walk: the Plan-bound Device has no located-in Enclosure of
    its own; its Unit PARENT is located in a NotPermitted Enclosure. The
    ancestor walk collects the parent's located-in pointer, so the gate sees
    the Enclosure and blocks the Run. This is the load-bearing case L-pre-1
    exists for."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, asset_id = _setup_chain(client)
        enclosure_id = uuid4()
        enclosure_lookup = InMemoryEnclosureLookup()
        enclosure_lookup.register(
            enclosure_id=enclosure_id,
            name="Beamline-Hutch",
            permit_status="NotPermitted",
            lifecycle="Active",
        )
        asset_lookup = _seed_child_parent_asset_lookup(asset_id, enclosure_id)
        _install_lookups(app, asset_lookup=asset_lookup, enclosure_lookup=enclosure_lookup)
        response = client.post(
            "/runs",
            json={"name": "ancestor-blocked", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "Enclosure" in detail
    assert "one or more referencing Enclosures" in detail


@pytest.mark.contract
def test_post_runs_returns_201_when_ancestor_enclosure_is_permitted() -> None:
    """Inheritance walk, paired happy path: the same ancestor's located-in
    Enclosure, now Permitted + Active, admits the Run."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, asset_id = _setup_chain(client)
        enclosure_id = uuid4()
        enclosure_lookup = InMemoryEnclosureLookup()
        enclosure_lookup.register(
            enclosure_id=enclosure_id,
            name="Beamline-Hutch",
            permit_status="Permitted",
            lifecycle="Active",
        )
        asset_lookup = _seed_child_parent_asset_lookup(asset_id, enclosure_id)
        _install_lookups(app, asset_lookup=asset_lookup, enclosure_lookup=enclosure_lookup)
        response = client.post(
            "/runs",
            json={"name": "ancestor-permitted", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_runs_ancestor_enclosure_silently_passes_without_the_walk() -> None:
    """Load-bearing proof: with the asset_lookup left EMPTY (no chain to
    climb), the very same parent's NotPermitted located-in Enclosure does NOT
    gate the Run -- it silently passes (201). This is exactly the gap the
    chain walk closes; the contrast with the 409 test above is the proof that
    the walk, not a direct match, is what makes L-pre-1 load-bearing."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, _asset_id = _setup_chain(client)
        enclosure_id = uuid4()
        enclosure_lookup = InMemoryEnclosureLookup()
        enclosure_lookup.register(
            enclosure_id=enclosure_id,
            name="Beamline-Hutch",
            permit_status="NotPermitted",
            lifecycle="Active",
        )
        # NOTE: asset_lookup is NOT installed -> it stays the empty default,
        # so ancestors_of returns nothing, no located-in pointer is
        # collected, and the gate's id-set is empty.
        _install_lookups(app, enclosure_lookup=enclosure_lookup)
        response = client.post(
            "/runs",
            json={"name": "ancestor-silent-pass", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_runs_returns_409_when_binding_enclosure_is_decommissioned() -> None:
    """A Decommissioned row reaching the decider fails defensively."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id, asset_id = _setup_chain(client)
        enclosure_id = uuid4()
        asset_lookup = _seed_located_in_asset_lookup(asset_id, enclosure_id)

        # InMemoryEnclosureLookup.find_by_ids filters by lifecycle ==
        # "Active" (mirrors the production adapter), so an injected
        # Decommissioned row is naturally excluded at the read layer.
        # Patch the adapter directly to return it anyway so the decider's
        # defensive guard is the path under test (a future production
        # adapter could be a different implementation that does not filter).
        decommissioned_row = EnclosureLookupResult(
            enclosure_id=enclosure_id,
            name="A-Hutch",
            permit_status="Permitted",
            lifecycle="Decommissioned",
            observed_at=None,
            source_kind=None,
            source_id=None,
        )

        class _AlwaysReturnLookup:
            async def lookup(self, enclosure_id):  # type: ignore[no-untyped-def]
                return None

            async def find_by_ids(
                self, *, enclosure_ids: frozenset[UUID]
            ) -> list[EnclosureLookupResult]:
                del enclosure_ids
                return [decommissioned_row]

        _install_lookups(app, asset_lookup=asset_lookup, enclosure_lookup=_AlwaysReturnLookup())  # type: ignore[arg-type]
        response = client.post(
            "/runs",
            json={"name": "tombstoned", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "Enclosure" in detail
    assert "one or more referencing Enclosures" in detail
