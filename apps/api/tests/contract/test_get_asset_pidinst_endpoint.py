"""Contract tests for `GET /assets/{asset_id}/pidinst`.

Slice E.1 of project_asset_persistent_id_design. Pins the HTTP route
layer + the per-error handler-tuple registrations in
`equipment/routes.py` (Lock 7 + Lock 8 + Lock 9). A regression that
drops the registration tuple would silently surface 500 here,
failing these tests.

Body shape follows the BC convention `{"detail": str(exc)}` for
every aggregate handler (see `_handle_validation_error`,
`_handle_cannot_transition`, `_handle_not_found` in
`equipment/routes.py`). Memo Section 7.3's earlier suggestion of a
richer `{"code": ..., "asset_id": ...}` body was over-specified; the
shipped shape is the BC-uniform `{"detail": ...}` shape.

The deeper closure-proof suite at
`tests/integration/test_get_asset_pidinst_handler_postgres.py` pins
the handler + assembler + projection chain end-to-end without
incurring HTTP overhead. This file is the orthogonal half: it pins
the route layer + status-code mapping that the handler-level tests
cannot reach.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset_unit(client: TestClient) -> UUID:
    response = client.post(
        "/assets",
        json={"name": "APS-2BM", "tier": "Unit", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["asset_id"])


@pytest.mark.contract
def test_get_asset_pidinst_returns_404_for_unknown_asset_id() -> None:
    """Pins Lock 8: AssetNotFoundError -> 404 via the shared
    `_handle_not_found` registration (asset never registered).
    """
    with TestClient(create_app()) as client:
        response = client.get(f"/assets/{uuid4()}/pidinst")

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.contract
def test_get_asset_pidinst_returns_409_for_asset_with_no_owners() -> None:
    """Pins Lock 8 + Lock 9: OwnerStateNotAvailableError -> 409 via
    the `_handle_pidinst_state_not_available` registration.

    A regression that drops `OwnerStateNotAvailableError` from the
    registration tuple in `equipment/routes.py` would surface 500
    here, failing the test. This is the load-bearing reason the
    contract suite exists alongside the handler-direct integration
    suite.
    """
    with TestClient(create_app()) as client:
        asset_id = _register_asset_unit(client)

        response = client.get(f"/assets/{asset_id}/pidinst")

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert "owner" in body["detail"].lower()


@pytest.mark.contract
def test_get_asset_pidinst_returns_409_for_asset_with_owner_but_no_model() -> None:
    """Pins the SECOND handler-registration entry in the same tuple:
    ManufacturerStateNotAvailableError -> 409 via
    `_handle_pidinst_state_not_available`.

    Registers an asset, adds an owner (clears the
    OwnerStateNotAvailable path), then GETs without binding a
    Model (Manufacturer source missing). The serializer raises
    ManufacturerStateNotAvailableError, which the registered handler
    maps to 409. A regression that drops
    ManufacturerStateNotAvailableError from the tuple surfaces 500
    here.
    """
    with TestClient(create_app()) as client:
        asset_id = _register_asset_unit(client)

        owner_response = client.post(
            f"/assets/{asset_id}/add-owner",
            json={"owner": {"name": "Helmholtz-Zentrum Berlin"}},
        )
        assert owner_response.status_code == 201, owner_response.text

        response = client.get(f"/assets/{asset_id}/pidinst")

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert "manufacturer" in body["detail"].lower()


@pytest.mark.contract
def test_get_asset_pidinst_route_path_matches_locked_shape() -> None:
    """Pins Lock 7: route path `GET /assets/{asset_id}/pidinst`
    (no `/equipment` prefix; the Equipment BC router mounts at
    `/assets/...`). A path rename or accidental `/equipment/...`
    prefix would 404 on the correct path and pass on the wrong one,
    flipping the assertions below.
    """
    with TestClient(create_app()) as client:
        asset_id = _register_asset_unit(client)

        canonical_response = client.get(f"/assets/{asset_id}/pidinst")
        prefixed_response = client.get(f"/equipment/assets/{asset_id}/pidinst")

    assert canonical_response.status_code == 409
    assert prefixed_response.status_code == 404
