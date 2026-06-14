"""Contract tests for `POST /assemblies/{assembly_id}/add-presents-as`.

Action endpoint with body `{role_id}`. 204 on success; 404 if
Assembly or Role not found; 409 on strict-not-idempotent.

## Test-env Role seeding

In `app_env=test` the projection worker does not run, so a POST
to /roles writes the event but does NOT populate the in-memory
RoleLookup. The `_create_detector_role` helper therefore both POSTs
the role AND seeds the in-memory adapter directly via
`app.state.deps.role_lookup.register(...)`. Same pattern as
test_add_family_presents_as_endpoint.py.
"""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_family(client: TestClient, name: str = "Imager") -> UUID:
    response = client.post(
        "/families",
        json={"name": name, "affordances": []},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["family_id"])


def _define_assembly(
    client: TestClient,
    family_id: UUID,
    *,
    name: str = "Microscope",
) -> UUID:
    response = client.post(
        "/assemblies",
        json={
            "name": name,
            "presents_as_family_id": str(family_id),
            "required_slots": [],
            "required_wires": [],
        },
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["assembly_id"])


def _create_detector_role(client: TestClient, app: FastAPI) -> UUID:
    response = client.post(
        "/roles",
        json={
            "name": "Diagnostician",
            "docstring": "Acquires 2D image frames.",
            "required_affordances": ["Imageable"],
            "optional_affordances": [],
            "produces": [],
            "consumes": [],
        },
    )
    assert response.status_code == 201, response.text
    role_id = UUID(response.json()["role_id"])
    app.state.deps.role_lookup.register(
        role_id=role_id,
        name="Detector",
        required_affordances=["Imageable"],
    )
    return role_id


@pytest.mark.contract
def test_post_add_presents_as_returns_204_on_success() -> None:
    app = create_app()
    with TestClient(app) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        role_id = _create_detector_role(client, app)
        response = client.post(
            f"/assemblies/{assembly_id}/add-presents-as",
            json={"role_id": str(role_id)},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_add_presents_as_returns_404_for_missing_assembly() -> None:
    app = create_app()
    with TestClient(app) as client:
        role_id = _create_detector_role(client, app)
        response = client.post(
            "/assemblies/00000000-0000-0000-0000-000000000999/add-presents-as",
            json={"role_id": str(role_id)},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_presents_as_returns_404_for_missing_role() -> None:
    app = create_app()
    with TestClient(app) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/add-presents-as",
            json={"role_id": "00000000-0000-0000-0000-000000000999"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_presents_as_returns_409_on_strict_not_idempotent_retry() -> None:
    app = create_app()
    with TestClient(app) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        role_id = _create_detector_role(client, app)
        body = {"role_id": str(role_id)}
        first = client.post(f"/assemblies/{assembly_id}/add-presents-as", json=body)
        second = client.post(f"/assemblies/{assembly_id}/add-presents-as", json=body)
    assert first.status_code == 204
    assert second.status_code == 409


@pytest.mark.contract
def test_post_add_presents_as_rejects_malformed_role_id_with_422() -> None:
    app = create_app()
    with TestClient(app) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/add-presents-as",
            json={"role_id": "not-a-uuid"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_presents_as_does_not_enforce_affordance_check() -> None:
    """3C scope: even when the Role declares Affordances the Assembly's
    constituents do not necessarily cover, the add succeeds. The
    affordance-superset gate is deferred to register_fixture layer
    per memo Watch item."""
    app = create_app()
    with TestClient(app) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        # Role requires Imageable + Streamable; the Assembly's
        # template carries NO affordance information at all.
        role_resp = client.post(
            "/roles",
            json={
                "name": "DemandingImager",
                "docstring": "Requires lots of things.",
                "required_affordances": ["Imageable", "Streamable"],
                "optional_affordances": [],
                "produces": [],
                "consumes": [],
            },
        )
        role_id = UUID(role_resp.json()["role_id"])
        app.state.deps.role_lookup.register(
            role_id=role_id,
            name="DemandingImager",
            required_affordances=["Imageable", "Streamable"],
        )
        response = client.post(
            f"/assemblies/{assembly_id}/add-presents-as",
            json={"role_id": str(role_id)},
        )
    # No affordance-superset check at template time -> 204.
    assert response.status_code == 204, response.text
