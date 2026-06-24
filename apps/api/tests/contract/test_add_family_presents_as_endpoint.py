"""Contract tests for `POST /families/{family_id}/add-presents-as`.

Action endpoint with body `{role_id}`. 204 on success; 404 if
Family or Role not found; 409 on already-advertised, missing
required affordances, or strict-not-idempotent retry.

## Test-env Role seeding

In `app_env=test` the projection worker does not run, so a POST to
/roles writes the event but does NOT populate the in-memory
RoleLookup the handler reads. The `_create_role` helper therefore
both POSTs the role AND seeds the in-memory adapter directly via
`app.state.deps.role_lookup.register(...)`. Same pattern as
test_add_asset_family_endpoint.py reaching into `app.state.deps` to
seed cross-aggregate state.

The Role name is a NON-SEED name ("Diagnostician") so it does not
collide with the 5 SEED_ROLES (Detector / Positioner / Controller /
Sensor / Regulator) bootstrap_equipment seeds at lifespan -- those occupy
their own uuid5-derived streams and a POST /roles with a seed name
returns 409.
"""

from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _create_camera_family(client: TestClient) -> str:
    response = client.post(
        "/families",
        json={"name": "Camera", "affordances": ["Imageable", "Binnable"]},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["family_id"])


def _create_role(
    client: TestClient,
    app: FastAPI,
    *,
    required: list[str],
) -> str:
    response = client.post(
        "/roles",
        json={
            "name": "Diagnostician",
            "docstring": "Acquires 2D image frames.",
            "required_affordances": required,
            "optional_affordances": [],
            "produces": [],
            "consumes": [],
        },
    )
    assert response.status_code == 201, response.text
    role_id = str(response.json()["role_id"])
    # Seed the in-memory RoleLookup so the handler edge can resolve
    # the new Role (no projection worker in app_env=test).
    deps = app.state.deps
    deps.role_lookup.register(
        role_id=UUID(role_id),
        name="Diagnostician",
        required_affordances=required,
    )
    return role_id


@pytest.mark.contract
def test_post_add_presents_as_returns_204_on_success() -> None:
    app = create_app()
    with TestClient(app) as client:
        family_id = _create_camera_family(client)
        role_id = _create_role(client, app, required=["Imageable"])
        response = client.post(
            f"/families/{family_id}/add-presents-as",
            json={"role_id": role_id},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_add_presents_as_returns_404_for_missing_family() -> None:
    app = create_app()
    with TestClient(app) as client:
        role_id = _create_role(client, app, required=[])
        response = client.post(
            "/families/00000000-0000-0000-0000-000000000999/add-presents-as",
            json={"role_id": role_id},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_presents_as_returns_404_for_missing_role() -> None:
    app = create_app()
    with TestClient(app) as client:
        family_id = _create_camera_family(client)
        response = client.post(
            f"/families/{family_id}/add-presents-as",
            json={"role_id": "00000000-0000-0000-0000-000000000999"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_presents_as_returns_409_when_family_missing_required_affordances() -> None:
    """Camera has Imageable + Binnable; Role requires {Imageable, Streamable}
    -- missing Streamable triggers FamilyCannotPresentAsError."""
    app = create_app()
    with TestClient(app) as client:
        family_id = _create_camera_family(client)
        role_id = _create_role(client, app, required=["Imageable", "Streamable"])
        response = client.post(
            f"/families/{family_id}/add-presents-as",
            json={"role_id": role_id},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_add_presents_as_returns_409_on_strict_not_idempotent_retry() -> None:
    app = create_app()
    with TestClient(app) as client:
        family_id = _create_camera_family(client)
        role_id = _create_role(client, app, required=["Imageable"])
        body: dict[str, Any] = {"role_id": role_id}
        first = client.post(f"/families/{family_id}/add-presents-as", json=body)
        second = client.post(f"/families/{family_id}/add-presents-as", json=body)
    assert first.status_code == 204
    assert second.status_code == 409


@pytest.mark.contract
def test_post_add_presents_as_rejects_malformed_role_id_with_422() -> None:
    app = create_app()
    with TestClient(app) as client:
        family_id = _create_camera_family(client)
        response = client.post(
            f"/families/{family_id}/add-presents-as",
            json={"role_id": "not-a-uuid"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_presents_as_rejects_malformed_path_id_with_422() -> None:
    app = create_app()
    with TestClient(app) as client:
        role_id = _create_role(client, app, required=[])
        response = client.post(
            "/families/not-a-uuid/add-presents-as",
            json={"role_id": role_id},
        )
    assert response.status_code == 422
    UUID(role_id)  # ensures fixture computed a real UUID
