"""HTTP route tests for `POST /fixtures/{fixture_id}/assign-persistent-identifier`.

Full status-code matrix per [[project-fixture-pidinst-design]] Section
15.2 + Locks L17 / L18 / L19:

  - 201 happy paths (DOI suffix, DOI auto-suffix, Handle suffix)
  - 201 response body echoes (scheme, value) verbatim
  - 404 when the fixture stream is missing
  - 409 when the fixture already carries a persistent_id (set-once)
  - 422 wire-layer validation (empty suffix, missing scheme)
  - 502 when the upstream DoiMinter raises PersistentIdentifierMintError
    (RaisingDoiMinter fixture from conftest, swapped onto the bound
    handler via dataclasses.replace per slice F Lock 10)
  - Event-store persistence pin (the FixturePersistentIdAssigned event
    lands on the Fixture stream)
  - Projection-shape lock (the persisted event payload carries the
    keys the FixtureSummaryProjection consumes; projection worker is
    not booted in test mode per the Asset-tier sibling precedent)

Sibling pattern to `test_assign_asset_persistent_id_route.py`; reuses
the conftest `raising_doi_minter` fixture introduced for the Asset
slice F 502 path.

In-memory adapters: `APP_ENV=test` is set in `tests/conftest.py`, so
`create_app()` builds the kernel with `InMemoryEventStore` and the
Equipment BC wires `StubDoiMinter` by default.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.features import assign_fixture_persistent_id
from tests.integration.equipment.conftest import RaisingDoiMinter

if TYPE_CHECKING:
    from cora.equipment.wire import EquipmentHandlers

pytestmark = pytest.mark.timeout(60, method="thread")

_STUB_DOI_PREFIX = "10.0000/cora-stub"
_STUB_HANDLE_PREFIX = "20.500.0000/cora-stub"


def _define_family(client: TestClient, *, name: str = "Camera") -> str:
    response = client.post(
        "/families",
        json={"name": name, "affordances": []},
    )
    assert response.status_code == 201, response.text
    family_id: str = response.json()["family_id"]
    return family_id


def _register_asset(client: TestClient, family_id: str, *, name: str = "Camera-1") -> str:
    response = client.post(
        "/assets",
        json={"name": name, "tier": "Device", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["asset_id"]
    add_family = client.post(
        f"/assets/{asset_id}/add-family",
        json={"family_id": family_id},
    )
    assert add_family.status_code == 204, add_family.text
    return asset_id


def _define_assembly(client: TestClient, family_id: str, *, name: str = "MCTOptics") -> str:
    body = {
        "name": name,
        "presents_as_family_id": family_id,
        "required_slots": [
            {
                "slot_name": "camera",
                "required_family_ids": [family_id],
                "cardinality": "Exactly1",
            }
        ],
        "required_wires": [],
    }
    response = client.post("/assemblies", json=body)
    assert response.status_code == 201, response.text
    assembly_id: str = response.json()["assembly_id"]
    return assembly_id


def _register_fixture(client: TestClient) -> str:
    """Seed Family + Asset + Assembly through the HTTP routes, return fixture_id."""
    family_id = _define_family(client)
    asset_id = _register_asset(client, family_id)
    assembly_id = _define_assembly(client, family_id)
    response = client.post(
        f"/assemblies/{assembly_id}/fixtures",
        json={
            "slot_asset_bindings": [
                {"slot_name": "camera", "asset_id": asset_id},
            ],
            "parameter_overrides": {},
        },
    )
    assert response.status_code == 201, response.text
    fixture_id: str = response.json()["fixture_id"]
    return fixture_id


def _swap_doi_minter(app: FastAPI, minter: object) -> None:
    """Rebuild the assign_fixture_persistent_id handler over a swapped minter.

    The handler closes over `deps.equipment.doi_minter` at bind time, so
    mutating the SimpleNamespace alone is not enough: the live handler
    on `app.state.equipment.assign_fixture_persistent_id` was bound
    before the swap. We mutate the BC-local namespace AND rebind the
    handler, then drop a fresh `EquipmentHandlers` onto
    `app.state.equipment` so the route's
    `request.app.state.equipment.assign_fixture_persistent_id` resolves
    to the rebound closure.
    """
    deps = app.state.deps
    object.__setattr__(deps.equipment, "doi_minter", minter)
    rebound = assign_fixture_persistent_id.bind(deps)
    handlers: EquipmentHandlers = app.state.equipment
    app.state.equipment = replace(handlers, assign_fixture_persistent_id=rebound, doi_minter=minter)


@pytest.mark.integration
def test_post_assign_fixture_pid_with_doi_scheme_and_suffix_returns_201_and_echoes_value() -> None:
    with TestClient(create_app()) as client:
        fixture_id = _register_fixture(client)
        response = client.post(
            f"/fixtures/{fixture_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "APS-2BM-FIX-001"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["scheme"] == "DOI"
    assert body["value"] == f"{_STUB_DOI_PREFIX}/APS-2BM-FIX-001"


@pytest.mark.integration
def test_post_assign_fixture_pid_with_doi_scheme_and_no_suffix_uses_stub_uuid_suffix() -> None:
    with TestClient(create_app()) as client:
        fixture_id = _register_fixture(client)
        response = client.post(
            f"/fixtures/{fixture_id}/assign-persistent-identifier",
            json={"scheme": "DOI"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["scheme"] == "DOI"
    assert body["value"].startswith(f"{_STUB_DOI_PREFIX}/")
    suffix = body["value"].removeprefix(f"{_STUB_DOI_PREFIX}/")
    assert len(suffix) == 36


@pytest.mark.integration
def test_post_assign_fixture_pid_with_handle_scheme_returns_201_with_handle_test_prefix() -> None:
    with TestClient(create_app()) as client:
        fixture_id = _register_fixture(client)
        response = client.post(
            f"/fixtures/{fixture_id}/assign-persistent-identifier",
            json={"scheme": "Handle", "suffix": "12345"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["scheme"] == "Handle"
    assert body["value"] == f"{_STUB_HANDLE_PREFIX}/12345"


@pytest.mark.integration
def test_post_assign_fixture_pid_endpoint_201_response_body_echoes_scheme_and_value_exactly() -> (
    None
):
    """201 body equals {"scheme": ..., "value": ...} byte-for-byte.

    Catches the regression class where the handler returns the right VO
    but the route's `AssignFixturePersistentIdResponse(...)` drops or
    renames a field. Complements the contract-tier OpenAPI shape test.
    """
    with TestClient(create_app()) as client:
        fixture_id = _register_fixture(client)
        response = client.post(
            f"/fixtures/{fixture_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "FIX-EXACT-ECHO"},
        )
    assert response.status_code == 201, response.text
    assert response.json() == {
        "scheme": "DOI",
        "value": f"{_STUB_DOI_PREFIX}/FIX-EXACT-ECHO",
    }


@pytest.mark.integration
def test_post_assign_fixture_persistent_id_with_unknown_fixture_returns_404() -> None:
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/fixtures/{missing}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "X"},
        )
    assert response.status_code == 404
    assert missing in response.json()["detail"]


@pytest.mark.integration
def test_post_assign_fixture_persistent_id_with_already_assigned_fixture_returns_409() -> None:
    with TestClient(create_app()) as client:
        fixture_id = _register_fixture(client)
        first = client.post(
            f"/fixtures/{fixture_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "FIRST"},
        )
        assert first.status_code == 201, first.text
        second = client.post(
            f"/fixtures/{fixture_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "SECOND"},
        )
    assert second.status_code == 409
    body = second.json()
    assert "detail" in body
    assert "FIRST" in body["detail"] or "SECOND" in body["detail"]


@pytest.mark.integration
def test_post_assign_fixture_persistent_id_with_empty_suffix_returns_422() -> None:
    with TestClient(create_app()) as client:
        fixture_id = _register_fixture(client)
        response = client.post(
            f"/fixtures/{fixture_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": ""},
        )
    assert response.status_code == 422


@pytest.mark.integration
def test_post_assign_fixture_persistent_id_with_missing_scheme_returns_422() -> None:
    with TestClient(create_app()) as client:
        fixture_id = _register_fixture(client)
        response = client.post(
            f"/fixtures/{fixture_id}/assign-persistent-identifier",
            json={"suffix": "X"},
        )
    assert response.status_code == 422


@pytest.mark.integration
def test_post_assign_fixture_persistent_id_persists_event_to_event_store() -> None:
    """The FixturePersistentIdAssigned event lands on the Fixture stream."""
    app = create_app()
    with TestClient(app) as client:
        fixture_id_str = _register_fixture(client)
        response = client.post(
            f"/fixtures/{fixture_id_str}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "PERSIST"},
        )
        assert response.status_code == 201, response.text
        fixture_id = UUID(fixture_id_str)
        events, _ = asyncio.run(app.state.deps.event_store.load("Fixture", fixture_id))
    event_types = [event.event_type for event in events]
    assert "FixturePersistentIdAssigned" in event_types
    assigned = next(event for event in events if event.event_type == "FixturePersistentIdAssigned")
    assert assigned.payload["persistent_id_scheme"] == "DOI"
    assert assigned.payload["persistent_id_value"] == f"{_STUB_DOI_PREFIX}/PERSIST"


@pytest.mark.integration
def test_post_assign_fixture_persistent_id_writes_persistent_id_to_projection_after_replay() -> (
    None
):
    """Pin the integration contract: persisted event shape feeds the projection.

    In test mode the projection worker does not run (no Postgres), so
    the projection's behavior is verified at the unit tier. This
    route-tier test asserts the event the route persists is SHAPED
    CORRECTLY for `FixtureSummaryProjection` to consume (scheme + value
    primitives, fixture_id matching the stream). Combined with the
    unit projection test, the end-to-end replay path is covered.
    """
    app = create_app()
    with TestClient(app) as client:
        fixture_id_str = _register_fixture(client)
        response = client.post(
            f"/fixtures/{fixture_id_str}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "REPLAY"},
        )
        assert response.status_code == 201, response.text
        fixture_id = UUID(fixture_id_str)
        events, _ = asyncio.run(app.state.deps.event_store.load("Fixture", fixture_id))
    assigned = next(event for event in events if event.event_type == "FixturePersistentIdAssigned")
    assert assigned.payload["fixture_id"] == fixture_id_str
    assert set(assigned.payload.keys()) >= {
        "fixture_id",
        "persistent_id_scheme",
        "persistent_id_value",
        "occurred_at",
    }


@pytest.mark.integration
def test_post_assign_fixture_persistent_id_with_raising_minter_returns_502(
    raising_doi_minter: RaisingDoiMinter,
) -> None:
    """Override the bound minter with RaisingDoiMinter and assert 502.

    Verifies the L19 mapping wires correctly: a
    `PersistentIdentifierMintError` raised by the upstream port surfaces
    as HTTP 502 with a `{"detail": ...}` body per L18 BC-uniform shape.
    The 502 exception handler is shared between Asset- and Fixture-tier
    mint flows per Lock 5 (one mapping serves both callers).
    """
    app = create_app()
    with TestClient(app) as client:
        fixture_id = _register_fixture(client)
        _swap_doi_minter(app, raising_doi_minter)
        response = client.post(
            f"/fixtures/{fixture_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "WILL-FAIL"},
        )
    assert response.status_code == 502
    body = response.json()
    assert "detail" in body
    assert "upstream stub failure" in body["detail"]
