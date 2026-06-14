"""Contract tests for the cross-BC Enclosure pre-flight gate on
POST /procedures/{procedure_id}/start.

Pins the wire-level behavior of the located-in Enclosure pre-flight gate
on the Procedure side. Mirrors test_start_run_enclosure_preflight.py
exactly:
  - 204 happy path (facility-envelope procedure, empty
    target_asset_ids) -- Permit-by-default per L-pre-1.
  - 204 happy path (procedure whose target Asset is located in an
    Active+Permitted Enclosure).
  - 409 NotPermitted: the Enclosure the target Asset is located in is
    permit_status="NotPermitted" -> ProcedureRequiresPermittedEnclosureError.
  - 409 Unknown: same shape with permit_status="Unknown".
  - 409 Decommissioned: the row reaching the decider has
    lifecycle="Decommissioned" -> defensive fail.
  - 409 CoverageMismatch: two target Assets located in two Enclosures,
    one Permitted+Active and one NotPermitted+Active -> mixed-status
    failure surfaces ProcedureEnclosureCoverageMismatchError.

The new mental model: an Asset declares the Enclosure it sits in via
`located_in_enclosure_id`, surfaced on the AssetLookup projection row.
The Procedure handler walks the target Asset ancestor closure
(`ancestors_of`), collects each row's `located_in_enclosure_id`, and
fetches those Enclosures by id (`find_by_ids`). A Device inherits the
located-in Enclosure of a parent Unit/Component. Tests seed the
`InMemoryAssetLookup` with the located-in pointer (the test app's
default asset_lookup is empty) and the `InMemoryEnclosureLookup` with
the matching enclosure row.

The 409 cases assert discriminating substrings drawn verbatim from
operation/aggregates/procedure/state.py error messages so the Requires
branch and the CoverageMismatch branch cannot pass each other's test.
"""

import dataclasses
from typing import Any
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
from tests.contract._subject_helpers import register_active_asset


def _register_procedure(client: TestClient, *, target_asset_ids: list[UUID] | None = None) -> UUID:
    body: dict[str, Any] = {"name": "Beam alignment", "kind": "alignment"}
    if target_asset_ids is not None:
        body["target_asset_ids"] = [str(a) for a in target_asset_ids]
    response = client.post("/procedures", json=body)
    assert response.status_code == 201, response.text
    return UUID(response.json()["procedure_id"])


def _install_lookups(app: FastAPI, *, asset_lookup=None, enclosure_lookup=None) -> None:  # type: ignore[no-untyped-def]
    """Swap asset_lookup and/or enclosure_lookup in one replace + re-wire.

    The test app's asset_lookup is an empty InMemoryAssetLookup, so the
    ancestor walk needs a seeded one carrying the located-in pointer the
    gate reads.
    """
    from cora.operation import wire_operation

    changes: dict[str, object] = {}
    if asset_lookup is not None:
        changes["asset_lookup"] = asset_lookup
    if enclosure_lookup is not None:
        changes["enclosure_lookup"] = enclosure_lookup
    new_deps = dataclasses.replace(app.state.deps, **changes)
    app.state.deps = new_deps
    app.state.operation = wire_operation(new_deps)


def _seed_located_in_asset_lookup(asset_id: UUID, enclosure_id: UUID) -> InMemoryAssetLookup:
    """Seed an AssetLookup so the target Asset is located in `enclosure_id`.

    The target Asset is registered as a root Unit (no parent) carrying
    the located-in pointer directly. In production the same field lives
    in proj_equipment_asset_summary.
    """
    lookup = InMemoryAssetLookup()
    lookup.register(
        asset_id,
        name="target-asset",
        tier="Unit",
        parent_id=None,
        located_in_enclosure_id=enclosure_id,
    )
    return lookup


def _seed_child_parent_asset_lookup(asset_id: UUID, enclosure_id: UUID) -> InMemoryAssetLookup:
    """Seed an AssetLookup with `asset_id` as a Device under a Unit parent.

    The Unit parent carries the located-in pointer; the child Device has
    none of its own and inherits the parent's via the ancestor walk. In
    production the same edges live in proj_equipment_asset_summary.
    """
    parent_id = uuid4()
    lookup = InMemoryAssetLookup()
    lookup.register(asset_id, name="child-device", tier="Device", parent_id=parent_id)
    lookup.register(
        parent_id,
        name="beamline-unit",
        tier="Unit",
        parent_id=None,
        located_in_enclosure_id=enclosure_id,
    )
    return lookup


@pytest.mark.contract
def test_post_start_procedure_returns_409_when_ancestor_enclosure_is_not_permitted() -> None:
    """Inheritance walk: the target Device has no located-in Enclosure of its
    own; its Unit PARENT is located in a NotPermitted Enclosure. The ancestor
    walk collects the parent's located-in pointer and blocks the Procedure --
    the Procedure-side mirror of the Run gate, closing the same silent-pass
    gap on the Procedure path."""
    app = create_app()
    with TestClient(app) as client:
        asset_id = UUID(register_active_asset(client))
        pid = _register_procedure(client, target_asset_ids=[asset_id])
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
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "one or more referencing Enclosures are not Permitted-and-Active" in detail


@pytest.mark.contract
def test_post_start_procedure_returns_204_when_ancestor_enclosure_is_permitted() -> None:
    """Inheritance walk, paired happy path: the same ancestor's located-in
    Enclosure, Permitted + Active, admits the Procedure."""
    app = create_app()
    with TestClient(app) as client:
        asset_id = UUID(register_active_asset(client))
        pid = _register_procedure(client, target_asset_ids=[asset_id])
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
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_start_procedure_ancestor_enclosure_silently_passes_without_the_walk() -> None:
    """Load-bearing proof on the Procedure path: with asset_lookup left EMPTY
    (no chain to climb), the same parent's NotPermitted located-in Enclosure
    does NOT gate the Procedure (204). The contrast with the 409 test proves
    the walk is what makes L-pre-1 load-bearing for Procedures too."""
    app = create_app()
    with TestClient(app) as client:
        asset_id = UUID(register_active_asset(client))
        pid = _register_procedure(client, target_asset_ids=[asset_id])
        enclosure_id = uuid4()
        enclosure_lookup = InMemoryEnclosureLookup()
        enclosure_lookup.register(
            enclosure_id=enclosure_id,
            name="Beamline-Hutch",
            permit_status="NotPermitted",
            lifecycle="Active",
        )
        # asset_lookup NOT installed -> empty default -> walk collects no
        # located-in pointer, so the gate's id-set is empty.
        _install_lookups(app, enclosure_lookup=enclosure_lookup)
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_start_procedure_returns_204_for_facility_envelope_procedure() -> None:
    """Permit-by-default happy path: a facility-envelope Procedure with
    empty target_asset_ids walks an empty asset_ids set -> [] rows ->
    gate trivially passes."""
    app = create_app()
    with TestClient(app) as client:
        pid = _register_procedure(client)
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_start_procedure_returns_204_when_binding_enclosure_is_permitted() -> None:
    """Active+Permitted located-in Enclosure: the gate accepts the row."""
    app = create_app()
    with TestClient(app) as client:
        asset_id = UUID(register_active_asset(client))
        pid = _register_procedure(client, target_asset_ids=[asset_id])
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
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 204, response.text


@pytest.mark.contract
@pytest.mark.parametrize("permit_status", ["NotPermitted", "Unknown"])
def test_post_start_procedure_returns_409_when_binding_enclosure_is_not_permitted(
    permit_status: str,
) -> None:
    """A non-Permitted located-in Enclosure raises 409
    ProcedureRequiresPermittedEnclosureError."""
    app = create_app()
    with TestClient(app) as client:
        asset_id = UUID(register_active_asset(client))
        pid = _register_procedure(client, target_asset_ids=[asset_id])
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
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "one or more referencing Enclosures are not Permitted-and-Active" in detail


@pytest.mark.contract
def test_post_start_procedure_returns_409_when_binding_enclosure_is_decommissioned() -> None:
    """A Decommissioned row reaching the decider fails defensively."""
    app = create_app()
    with TestClient(app) as client:
        asset_id = UUID(register_active_asset(client))
        pid = _register_procedure(client, target_asset_ids=[asset_id])
        enclosure_id = uuid4()
        asset_lookup = _seed_located_in_asset_lookup(asset_id, enclosure_id)

        # As in the start_run test: the in-memory adapter filters
        # Decommissioned at the read layer, so we hand-roll an adapter
        # that returns the row anyway to exercise the decider's
        # defensive lifecycle guard.
        from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult

        tombstoned = EnclosureLookupResult(
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
                return [tombstoned]

        _install_lookups(app, asset_lookup=asset_lookup, enclosure_lookup=_AlwaysReturnLookup())
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "one or more referencing Enclosures are not Permitted-and-Active" in detail


@pytest.mark.contract
def test_post_start_procedure_returns_409_for_mixed_status_bindings() -> None:
    """Mixed-status located-in Enclosures raise 409
    ProcedureEnclosureCoverageMismatchError.

    Two target Assets, each located in its own Enclosure: one
    Permitted+Active, one NotPermitted+Active. The decider's
    CoverageMismatch branch fires because some referencing rows pass and
    some fail.
    """
    app = create_app()
    with TestClient(app) as client:
        passing_asset_id = UUID(register_active_asset(client))
        failing_asset_id = UUID(register_active_asset(client))
        pid = _register_procedure(client, target_asset_ids=[passing_asset_id, failing_asset_id])
        pass_enclosure_id = uuid4()
        fail_enclosure_id = uuid4()
        enclosure_lookup = InMemoryEnclosureLookup()
        enclosure_lookup.register(
            enclosure_id=pass_enclosure_id,
            name="A-Hutch",
            permit_status="Permitted",
            lifecycle="Active",
        )
        enclosure_lookup.register(
            enclosure_id=fail_enclosure_id,
            name="B-Hutch",
            permit_status="NotPermitted",
            lifecycle="Active",
        )
        asset_lookup = InMemoryAssetLookup()
        asset_lookup.register(
            passing_asset_id,
            name="passing-asset",
            tier="Unit",
            parent_id=None,
            located_in_enclosure_id=pass_enclosure_id,
        )
        asset_lookup.register(
            failing_asset_id,
            name="failing-asset",
            tier="Unit",
            parent_id=None,
            located_in_enclosure_id=fail_enclosure_id,
        )
        _install_lookups(app, asset_lookup=asset_lookup, enclosure_lookup=enclosure_lookup)
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "failed the Permitted-and-Active gate" in detail
