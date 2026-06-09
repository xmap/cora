"""Contract tests for the cross-BC Enclosure pre-flight gate on
POST /procedures/{procedure_id}/start.

Pins the wire-level behavior of the gate added in Sub-Slice F.
Mirrors test_start_run_enclosure_preflight.py exactly:
  - 204 happy path (facility-envelope procedure, empty
    target_asset_ids) -- Permit-by-default per L-pre-1.
  - 204 happy path (procedure with target_asset_ids whose Enclosure
    binding is Active+Permitted).
  - 409 NotPermitted: the Enclosure binding the target Asset is
    permit_status="NotPermitted" -> ProcedureRequiresPermittedEnclosureError.
  - 409 Unknown: same shape with permit_status="Unknown".
  - 409 Decommissioned: the row reaching the decider has
    lifecycle="Decommissioned" -> defensive fail.
"""

import dataclasses
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
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


def _install_enclosure_lookup(app: FastAPI, lookup) -> None:  # type: ignore[no-untyped-def]
    """Swap the kernel's enclosure_lookup; re-wire the Operation handlers
    so they pick up the new deps."""
    from cora.operation import wire_operation

    new_deps = dataclasses.replace(app.state.deps, enclosure_lookup=lookup)
    app.state.deps = new_deps
    app.state.operation = wire_operation(new_deps)


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
    """Active+Permitted binding: the gate accepts the row."""
    app = create_app()
    with TestClient(app) as client:
        asset_id = UUID(register_active_asset(client))
        pid = _register_procedure(client, target_asset_ids=[asset_id])
        lookup = InMemoryEnclosureLookup()
        lookup.register(
            enclosure_id=uuid4(),
            name="A-Hutch",
            containing_asset_id=asset_id,
            permit_status="Permitted",
            lifecycle="Active",
        )
        _install_enclosure_lookup(app, lookup)
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 204, response.text


@pytest.mark.contract
@pytest.mark.parametrize("permit_status", ["NotPermitted", "Unknown"])
def test_post_start_procedure_returns_409_when_binding_enclosure_is_not_permitted(
    permit_status: str,
) -> None:
    """A non-Permitted binding raises 409
    ProcedureRequiresPermittedEnclosureError."""
    app = create_app()
    with TestClient(app) as client:
        asset_id = UUID(register_active_asset(client))
        pid = _register_procedure(client, target_asset_ids=[asset_id])
        lookup = InMemoryEnclosureLookup()
        lookup.register(
            enclosure_id=uuid4(),
            name="A-Hutch",
            containing_asset_id=asset_id,
            permit_status=permit_status,
            lifecycle="Active",
        )
        _install_enclosure_lookup(app, lookup)
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 409, response.text
    assert "Enclosure" in response.json()["detail"]


@pytest.mark.contract
def test_post_start_procedure_returns_409_when_binding_enclosure_is_decommissioned() -> None:
    """A Decommissioned row reaching the decider fails defensively."""
    app = create_app()
    with TestClient(app) as client:
        asset_id = UUID(register_active_asset(client))
        pid = _register_procedure(client, target_asset_ids=[asset_id])

        # As in the start_run test: the in-memory adapter filters
        # Decommissioned at the read layer, so we hand-roll an adapter
        # that returns the row anyway to exercise the decider's
        # defensive lifecycle guard.
        from cora.infrastructure.ports.enclosure_lookup import EnclosureReference

        tombstoned = EnclosureReference(
            enclosure_id=uuid4(),
            name="A-Hutch",
            containing_asset_id=asset_id,
            permit_status="Permitted",
            lifecycle="Decommissioned",
            observed_at=None,
            source_kind=None,
            source_id=None,
        )

        class _AlwaysReturnLookup:
            async def lookup(self, enclosure_id):  # type: ignore[no-untyped-def]
                return None

            async def find_for_assets(
                self, *, asset_ids: frozenset[UUID]
            ) -> list[EnclosureReference]:
                del asset_ids
                return [tombstoned]

        _install_enclosure_lookup(app, _AlwaysReturnLookup())
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 409, response.text
    assert "Enclosure" in response.json()["detail"]
