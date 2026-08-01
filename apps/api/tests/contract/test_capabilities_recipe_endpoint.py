"""Contract tests for the Recipe BC's Capability aggregate.

Distinct from `test_families_endpoint.py`, which covers the
Equipment-side Family aggregate (Capability renamed to Family on
the Equipment side). THIS file covers the Recipe BC Capability
aggregate.

Verifies request schema, response schema, status codes, and that
domain errors map correctly via the BC's exception handler.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_capabilities_returns_201_with_capability_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.flyscan",
                "name": "FlyScan Tomography",
                "required_affordances": ["Rotatable", "Triggerable"],
                "executor_shapes": ["Method"],
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert "capability_id" in body
    UUID(body["capability_id"])


@pytest.mark.contract
def test_post_capabilities_round_trips_into_get_capability_response() -> None:
    with TestClient(create_app()) as client:
        post = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.tomo",
                "name": "Tomography",
                "description": "Continuous-rotation tomography sweep.",
                "required_affordances": ["Rotatable", "Triggerable"],
                "executor_shapes": ["Method"],
            },
        )
        assert post.status_code == 201
        capability_id = post.json()["capability_id"]

        get = client.get(f"/capabilities/{capability_id}")

    assert get.status_code == 200
    body = get.json()
    assert body == {
        "id": capability_id,
        "code": "cora.capability.tomo",
        "name": "Tomography",
        "status": "Defined",
        "version": None,
        "description": "Continuous-rotation tomography sweep.",
        # Sorted alphabetically for determinism.
        "required_affordances": ["Rotatable", "Triggerable"],
        "executor_shapes": ["Method"],
        "parameters_schema": None,
        "replaced_by_capability_id": None,
        # Projection-sourced timestamps; null in contract tests (no DB pool).
        # Populated values asserted in tests/integration/test_get_capability_handler_postgres.py.
        "created_at": None,
        "versioned_at": None,
        "deprecated_at": None,
    }


@pytest.mark.contract
def test_post_capabilities_accepts_empty_required_affordances() -> None:
    """Pattern P: empty required_affordances is valid (parameter-driven Capabilities)."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.energy_change",
                "name": "Energy Change",
                "required_affordances": [],
                "executor_shapes": ["Method"],
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_capabilities_rejects_empty_executor_shapes_with_400() -> None:
    """A Capability with no executor kinds has no operational meaning."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.x",
                "name": "X",
                "required_affordances": [],
                "executor_shapes": [],
            },
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_capabilities_rejects_missing_namespace_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/capabilities",
            json={
                "code": "flyscan",
                "name": "FlyScan",
                "required_affordances": [],
                "executor_shapes": ["Method"],
            },
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_capabilities_rejects_unknown_affordance_with_422() -> None:
    """Pydantic enum-validation at the API boundary."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.x",
                "name": "X",
                "required_affordances": ["Bogus"],
                "executor_shapes": ["Method"],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_capabilities_rejects_unknown_executor_shape_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.x",
                "name": "X",
                "required_affordances": [],
                "executor_shapes": ["Workflow"],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_capabilities_rejects_missing_required_fields_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/capabilities",
            json={"code": "cora.capability.x", "name": "X"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_get_capabilities_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/capabilities/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.contract
def test_version_capability_round_trips_into_get_capability_response() -> None:
    """version_capability REPLACES declarative contract; get reflects new state."""
    with TestClient(create_app()) as client:
        post = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.v",
                "name": "V",
                "required_affordances": ["Rotatable"],
                "executor_shapes": ["Method"],
            },
        )
        capability_id = post.json()["capability_id"]

        version_resp = client.post(
            f"/capabilities/{capability_id}/version",
            json={
                "version_tag": "v2",
                "required_affordances": ["Imageable"],
                "executor_shapes": ["Method", "Procedure"],
            },
        )
        assert version_resp.status_code == 204

        get = client.get(f"/capabilities/{capability_id}")
    body = get.json()
    assert body["status"] == "Versioned"
    assert body["version"] == "v2"
    # Replace-on-version semantics: Rotatable is GONE, Imageable is present.
    assert body["required_affordances"] == ["Imageable"]
    assert body["executor_shapes"] == ["Method", "Procedure"]


@pytest.mark.contract
def test_deprecate_capability_with_replaced_by_pointer() -> None:
    with TestClient(create_app()) as client:
        post1 = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.original",
                "name": "Original",
                "required_affordances": [],
                "executor_shapes": ["Method"],
            },
        )
        original_id = post1.json()["capability_id"]
        post2 = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.successor",
                "name": "Successor",
                "required_affordances": [],
                "executor_shapes": ["Method"],
            },
        )
        successor_id = post2.json()["capability_id"]

        deprecate_resp = client.post(
            f"/capabilities/{original_id}/deprecate",
            json={"reason": "Superseded", "replaced_by_capability_id": successor_id},
        )
        assert deprecate_resp.status_code == 204

        get = client.get(f"/capabilities/{original_id}")
    body = get.json()
    assert body["status"] == "Deprecated"
    assert body["replaced_by_capability_id"] == successor_id


@pytest.mark.contract
def test_deprecate_capability_rejects_re_deprecation_with_409() -> None:
    with TestClient(create_app()) as client:
        post = client.post(
            "/capabilities",
            json={
                "code": "cora.capability.x",
                "name": "X",
                "required_affordances": [],
                "executor_shapes": ["Method"],
            },
        )
        capability_id = post.json()["capability_id"]
        first = client.post(
            f"/capabilities/{capability_id}/deprecate", json={"reason": "Superseded"}
        )
        assert first.status_code == 204
        second = client.post(
            f"/capabilities/{capability_id}/deprecate", json={"reason": "Superseded"}
        )
    assert second.status_code == 409
