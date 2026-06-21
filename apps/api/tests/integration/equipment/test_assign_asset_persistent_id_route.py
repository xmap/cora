"""HTTP route tests for `POST /assets/{asset_id}/assign-persistent-identifier`.

Full status-code matrix per slice F Section 13.2 + Locks L17 / L18 / L19:

  - 201 happy paths (DOI suffix, DOI auto-suffix, Handle suffix)
  - 201 response body echoes (scheme, value) verbatim (P2-18 HTTPX pin)
  - 404 when asset stream is missing
  - 409 when asset is Decommissioned
  - 409 when asset already carries a persistent_id (set-once)
  - 422 wire-layer validation (empty suffix, oversized suffix, missing
    scheme, unknown scheme value)
  - 502 when the upstream PersistentIdentifierMinter raises PersistentIdentifierMintError
    (RaisingPersistentIdentifierMinter fixture from conftest, swapped onto the bound
    handler via dataclasses.replace per Lock 10)
  - Event-store persistence pin (the AssetPersistentIdAssigned event
    lands on the Asset stream)
  - P2-24 foreign-prefix round-trip (pytest.skip until F.2 grows a
    register-existing mode on Stub)

In-memory adapters: `APP_ENV=test` is set in `tests/conftest.py`, so
`create_app()` builds the kernel with `InMemoryEventStore` and the
Equipment BC wires `StubPersistentIdentifierMinter` by default (no DataCite credentials
present in the test Settings).
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
from cora.equipment.features import assign_asset_persistent_id
from tests.integration.equipment.conftest import RaisingPersistentIdentifierMinter

if TYPE_CHECKING:
    from cora.equipment.wire import EquipmentHandlers

pytestmark = pytest.mark.timeout(60, method="thread")

_STUB_DOI_PREFIX = "10.0000/cora-stub"
_STUB_HANDLE_PREFIX = "20.500.0000/cora-stub"


def _register_asset(client: TestClient, *, name: str = "Detector-X") -> str:
    response = client.post(
        "/assets",
        json={"name": name, "tier": "Device", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["asset_id"]
    return asset_id


def _swap_persistent_identifier_minter(app: FastAPI, minter: object) -> None:
    """Rebuild the assign_asset_persistent_id handler over a swapped minter.

    The handler closes over `deps.equipment.persistent_identifier_minter` at bind time, so
    mutating the SimpleNamespace alone is not enough: the live handler
    on `app.state.equipment.assign_asset_persistent_id` was bound before the
    swap. We mutate the BC-local namespace AND rebind the handler, then
    drop a fresh `EquipmentHandlers` onto `app.state.equipment` so the
    route's `request.app.state.equipment.assign_asset_persistent_id` resolves
    to the rebound closure.
    """
    deps = app.state.deps
    object.__setattr__(deps.equipment, "persistent_identifier_minter", minter)
    rebound = assign_asset_persistent_id.bind(deps)
    handlers: EquipmentHandlers = app.state.equipment
    app.state.equipment = replace(
        handlers, assign_asset_persistent_id=rebound, persistent_identifier_minter=minter
    )


@pytest.mark.integration
def test_post_assign_persistent_id_with_doi_scheme_and_suffix_returns_201_and_echoes_value() -> (
    None
):
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "APS-2BM-CAM-001"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["scheme"] == "DOI"
    assert body["value"] == f"{_STUB_DOI_PREFIX}/APS-2BM-CAM-001"


@pytest.mark.integration
def test_post_assign_persistent_id_with_doi_scheme_and_no_suffix_uses_stub_uuid_suffix() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "DOI"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["scheme"] == "DOI"
    assert body["value"].startswith(f"{_STUB_DOI_PREFIX}/")
    # UUID4 suffix is 36 chars; assert a non-trivial server-generated tail.
    suffix = body["value"].removeprefix(f"{_STUB_DOI_PREFIX}/")
    assert len(suffix) == 36


@pytest.mark.integration
def test_post_assign_persistent_id_with_handle_scheme_returns_201_with_handle_test_prefix() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "Handle", "suffix": "12345"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["scheme"] == "Handle"
    assert body["value"] == f"{_STUB_HANDLE_PREFIX}/12345"


@pytest.mark.integration
def test_post_assign_persistent_id_endpoint_201_response_body_echoes_scheme_and_value_exactly() -> (
    None
):
    """P2-18 HTTPX wire pin: 201 body == {"scheme": ..., "value": ...}.

    Catches the regression class where the handler returns the right VO
    but the route's `AssignAssetPersistentIdResponse(...)` drops or renames a
    field. Complements the contract-tier OpenAPI shape test.
    """
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "APS-EXACT-ECHO"},
        )
    assert response.status_code == 201, response.text
    assert response.json() == {
        "scheme": "DOI",
        "value": f"{_STUB_DOI_PREFIX}/APS-EXACT-ECHO",
    }


@pytest.mark.integration
def test_post_assign_persistent_id_with_unknown_asset_returns_404() -> None:
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "X"},
        )
    assert response.status_code == 404
    assert missing in response.json()["detail"]


@pytest.mark.integration
def test_post_assign_persistent_id_with_decommissioned_asset_returns_409() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "X"},
        )
    assert response.status_code == 409
    assert "Decommissioned" in response.json()["detail"]


@pytest.mark.integration
def test_post_assign_persistent_id_with_already_assigned_asset_returns_409() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "FIRST"},
        )
        assert first.status_code == 201, first.text
        second = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "SECOND"},
        )
    assert second.status_code == 409
    body = second.json()
    assert "detail" in body
    assert "FIRST" in body["detail"] or "SECOND" in body["detail"]


@pytest.mark.integration
def test_post_assign_persistent_id_with_empty_suffix_returns_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": ""},
        )
    assert response.status_code == 422


@pytest.mark.integration
def test_post_assign_persistent_id_with_suffix_over_max_length_returns_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "x" * 201},
        )
    assert response.status_code == 422


@pytest.mark.integration
def test_post_assign_persistent_id_with_missing_scheme_returns_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"suffix": "X"},
        )
    assert response.status_code == 422


@pytest.mark.integration
def test_post_assign_persistent_id_with_invalid_scheme_value_returns_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "ARK", "suffix": "X"},
        )
    assert response.status_code == 422


@pytest.mark.integration
def test_post_assign_persistent_id_persists_event_to_event_store() -> None:
    """The AssetPersistentIdAssigned event lands on the Asset stream."""
    app = create_app()
    with TestClient(app) as client:
        asset_id_str = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id_str}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "PERSIST"},
        )
        assert response.status_code == 201, response.text
        asset_id = UUID(asset_id_str)
        events, _ = asyncio.run(app.state.deps.event_store.load("Asset", asset_id))
    event_types = [event.event_type for event in events]
    assert "AssetPersistentIdAssigned" in event_types
    assigned = next(event for event in events if event.event_type == "AssetPersistentIdAssigned")
    assert assigned.payload["persistent_id_scheme"] == "DOI"
    assert assigned.payload["persistent_id_value"] == f"{_STUB_DOI_PREFIX}/PERSIST"


@pytest.mark.integration
def test_post_assign_persistent_id_writes_persistent_id_to_projection_after_replay() -> None:
    """Apply the persisted event through the AssetSummaryProjection.

    In test mode the projection worker does not run (no Postgres), so
    the projection's behavior is verified at the unit tier
    (`test_assign_asset_persistent_id_summary_projection.py`). This route-tier
    test pins the integration contract: the event the route persists is
    SHAPED CORRECTLY for the projection to consume (scheme + value
    primitives, asset_id matching the stream). Combined with the unit
    projection test, the end-to-end replay path is covered.
    """
    app = create_app()
    with TestClient(app) as client:
        asset_id_str = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id_str}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "REPLAY"},
        )
        assert response.status_code == 201, response.text
        asset_id = UUID(asset_id_str)
        events, _ = asyncio.run(app.state.deps.event_store.load("Asset", asset_id))
    assigned = next(event for event in events if event.event_type == "AssetPersistentIdAssigned")
    assert assigned.payload["asset_id"] == asset_id_str
    assert set(assigned.payload.keys()) >= {
        "asset_id",
        "persistent_id_scheme",
        "persistent_id_value",
        "occurred_at",
    }


@pytest.mark.integration
def test_post_assign_persistent_id_with_raising_minter_returns_502(
    raising_persistent_identifier_minter: RaisingPersistentIdentifierMinter,
) -> None:
    """Override the bound minter with RaisingPersistentIdentifierMinter and assert 502.

    Verifies the L11 + L19 mapping wires correctly: a
    `PersistentIdentifierMintError` raised by the upstream port surfaces
    as HTTP 502 with a `{"detail": ...}` body per L18 BC-uniform shape.
    """
    app = create_app()
    with TestClient(app) as client:
        asset_id = _register_asset(client)
        _swap_persistent_identifier_minter(app, raising_persistent_identifier_minter)
        response = client.post(
            f"/assets/{asset_id}/assign-persistent-identifier",
            json={"scheme": "DOI", "suffix": "WILL-FAIL"},
        )
    assert response.status_code == 502
    body = response.json()
    assert "detail" in body
    assert "upstream stub failure" in body["detail"]


@pytest.mark.integration
def test_post_assign_persistent_id_with_operator_supplied_full_doi_round_trips_unchanged() -> None:
    """P2-24 foreign-prefix passthrough lock-in.

    Operator submits a suffix containing a foreign DOI prefix
    (`10.5281/zenodo.1234567`); the Stub adapter does NOT currently
    grow a register-existing mode in F.1 (its contract concatenates
    `<stub-prefix>/<suffix>` unconditionally). Locking the post-F.2
    wire format at F.1 lock time so the cassette suite does not have
    to re-design this surface.
    """
    pytest.skip(
        "foreign-prefix passthrough lands in F.2 via DataCite PUT idempotency; "
        "see project_asset_persistent_id_write_design Finding 24"
    )
