"""Contract tests for `POST /methods`.

Mirror of `test_families_endpoint.py`. Verifies request schema,
response schema, status codes, and that the whitespace-only-name
domain error maps to 400 via the BC's exception handler.

Pinned: needed_family_ids is required (use [] for procedural
Methods); empty list accepted; non-list rejected as 422.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.recipe.aggregates.method import (
    METHOD_NAME_MAX_LENGTH,
    MethodAlreadyExistsError,
)
from cora.recipe.features.define_method.route import (
    _get_handler as _get_define_method_handler,  # pyright: ignore[reportPrivateUsage]
)
from tests.contract._helpers import create_capability_via_api


@pytest.mark.contract
def test_post_methods_returns_201_with_method_id() -> None:
    cap1 = str(uuid4())
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={"name": "XRF Mapping", "capability_id": _cap_id, "needed_family_ids": [cap1]},
        )

    assert response.status_code == 201
    body = response.json()
    assert "method_id" in body
    UUID(body["method_id"])  # parses


@pytest.mark.contract
def test_post_methods_accepts_empty_needed_family_ids() -> None:
    """Procedural Methods (no equipment requirement)."""
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={"name": "Sample Cleaning", "capability_id": _cap_id, "needed_family_ids": []},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_methods_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={"name": "  XRF Mapping  ", "capability_id": _cap_id, "needed_family_ids": []},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_methods_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post("/methods", json={"needed_family_ids": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_rejects_missing_needed_family_ids_with_422() -> None:
    """needed_family_ids is required (no default at the API
    boundary); use [] explicitly for procedural Methods."""
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post("/methods", json={"name": "X"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods", json={"name": "", "capability_id": _cap_id, "needed_family_ids": []}
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={"name": "a" * 201, "capability_id": _cap_id, "needed_family_ids": []},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={"name": "   ", "capability_id": _cap_id, "needed_family_ids": []},
        )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_methods_accepts_needed_assembly_ids() -> None:
    """needed_assembly_ids is OPTIONAL on the request body (defaults to
    [] via Pydantic) and accepts a list of Assembly UUIDs. Pins the
    wire shape; eventual-consistency: ids are NOT verified against
    the Equipment Assembly stream at decide time."""
    asm_id = str(uuid4())
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={
                "name": "Microscope Tomography",
                "capability_id": _cap_id,
                "needed_family_ids": [],
                "needed_assembly_ids": [asm_id],
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_methods_accepts_omitted_needed_assembly_ids() -> None:
    """Backward-compat: existing callers that don't supply
    needed_assembly_ids keep working (defaults to [])."""
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={"name": "X", "capability_id": _cap_id, "needed_family_ids": []},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_methods_rejects_non_uuid_needed_assembly_with_422() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={
                "name": "X",
                "capability_id": _cap_id,
                "needed_family_ids": [],
                "needed_assembly_ids": ["not-a-uuid"],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_rejects_non_uuid_needed_family_with_422() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={"name": "X", "capability_id": _cap_id, "needed_family_ids": ["not-a-uuid"]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_methods_uses_max_length_constant_from_domain() -> None:
    """Pydantic max_length must track the domain METHOD_NAME_MAX_LENGTH constant."""
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={
                "name": "a" * METHOD_NAME_MAX_LENGTH,
                "capability_id": _cap_id,
                "needed_family_ids": [],
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_methods_accepts_family_ids_without_verifying_existence() -> None:
    """Eventual-consistency stance: bogus Family ids are accepted
    at decide time. Mismatch surfaces at Plan binding (6e). Pinned
    to lock the no-verification contract end-to-end."""
    bogus_cap = "01900000-0000-7000-8000-deadbeefcafe"
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={"name": "X", "capability_id": _cap_id, "needed_family_ids": [bogus_cap]},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_methods_returns_409_when_method_already_exists() -> None:
    """Defensive guard: MethodAlreadyExistsError -> 409. Same pattern
    as FamilyAlreadyExistsError. Stub the handler so the route's
    exception handler is verified end-to-end."""
    existing_id = uuid4()

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise MethodAlreadyExistsError(existing_id)

    app = create_app()
    app.dependency_overrides[_get_define_method_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            # The handler is stubbed to raise MethodAlreadyExistsError
            # before any Capability load, so capability_id can be any
            # well-formed UUID (no Capability stream seeding required).
            response = client.post(
                "/methods",
                json={"name": "X", "capability_id": str(uuid4()), "needed_family_ids": []},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert str(existing_id) in body["detail"]


@pytest.mark.contract
def test_post_methods_openapi_schema_marks_capability_id_required() -> None:
    """OpenAPI surface pin (final-coverage gate-review P2).

    `DefineMethod.capability_id` is REQUIRED, so the generated OpenAPI
    request schema for `POST /methods` must list `capability_id` in
    the `required` array of the `DefineMethodRequest` component
    schema. A future regression that re-defaults the field to None at
    the Pydantic layer would silently accept missing-capability_id
    POSTs (rejected at the decider, but with a less helpful 422
    instead of the schema-validation 422). Pinning the OpenAPI schema
    closes that surface."""
    with TestClient(create_app()) as client:
        openapi = client.get("/openapi.json").json()

    component = openapi["components"]["schemas"]["DefineMethodRequest"]
    assert "capability_id" in component["properties"], (
        "DefineMethodRequest must expose capability_id at the OpenAPI surface"
    )
    assert "capability_id" in component["required"], "capability_id is REQUIRED at the API boundary"
