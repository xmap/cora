"""Contract tests for `POST /roles`."""

from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _body(**overrides: object) -> dict[str, Any]:
    # Default name avoids the 4 SEED_ROLES (Imager, Positioner, Controller,
    # Detector) that bootstrap_equipment seeds at lifespan. POSTing a seed
    # name returns 409 by design (handler derives stream_id from name);
    # see test_post_roles_with_seed_role_name_returns_409.
    base: dict[str, Any] = {
        "name": "Diagnostician",
        "docstring": "Acquires 2D image frames on exposure or trigger.",
        "required_affordances": ["Imageable"],
        "optional_affordances": ["Binnable"],
        "produces": ["Image"],
        "consumes": ["TriggerIn"],
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_roles_returns_201_with_role_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/roles", json=_body())
    assert response.status_code == 201, response.text
    body = response.json()
    assert "role_id" in body
    UUID(body["role_id"])


@pytest.mark.contract
def test_post_roles_rejects_empty_name_with_422() -> None:
    """Pydantic schema validation fires before the decider."""
    with TestClient(create_app()) as client:
        response = client.post("/roles", json=_body(name=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_roles_rejects_whitespace_only_name_with_400() -> None:
    """Pydantic accepts a 1+ char body; the decider VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post("/roles", json=_body(name="   "))
    assert response.status_code == 400


@pytest.mark.contract
def test_post_roles_rejects_empty_docstring_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/roles", json=_body(docstring=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_roles_rejects_overlapping_affordance_sets_with_400() -> None:
    """Required and optional Affordance sets must be disjoint."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/roles",
            json=_body(
                required_affordances=["Imageable", "Binnable"],
                optional_affordances=["Binnable"],
            ),
        )
    assert response.status_code == 400, response.text


@pytest.mark.contract
def test_post_roles_rejects_too_long_signal_type_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/roles",
            json=_body(produces=["x" * 51]),
        )
    assert response.status_code == 400, response.text


@pytest.mark.contract
def test_post_roles_rejects_unknown_affordance_with_422() -> None:
    """Pydantic enum validation rejects unknown Affordance value strings."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/roles",
            json=_body(required_affordances=["NotARealAffordance"]),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_roles_accepts_empty_collections() -> None:
    """Empty required_affordances + optional_affordances + produces +
    consumes are all valid at the schema layer (operator may author a
    documentation-only contract; decider enforces disjointness only)."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/roles",
            json=_body(
                required_affordances=[],
                optional_affordances=[],
                produces=[],
                consumes=[],
            ),
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_roles_idempotency_key_reuse_returns_cached_response() -> None:
    """Same body + same key -> cached role_id; not re-created."""
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "role-it-key-1"}
        first = client.post("/roles", json=_body(name="Diagnostician"), headers=headers)
        second = client.post("/roles", json=_body(name="Diagnostician"), headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["role_id"] == second.json()["role_id"]


@pytest.mark.contract
def test_post_roles_idempotency_key_with_different_body_returns_422() -> None:
    """Same key + different body -> conflict (422)."""
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "role-it-key-2"}
        first = client.post("/roles", json=_body(name="Diagnostician"), headers=headers)
        second = client.post("/roles", json=_body(name="Cartographer"), headers=headers)
    assert first.status_code == 201
    assert second.status_code == 422


@pytest.mark.contract
def test_post_roles_with_seed_role_name_returns_409() -> None:
    """Seed Roles are auto-defined at lifespan via uuid5-derived stream_ids.

    POSTing one of {Imager, Positioner, Controller, Detector} races the
    seed for the same stream, surfacing as 409 (the event-store's
    expected_version=0 violation). Operators wanting a Role with the
    same SEMANTIC slot pick a different name; the contract content is
    already captured by the seed.
    """
    with TestClient(create_app()) as client:
        response = client.post("/roles", json=_body(name="Imager"))
    assert response.status_code == 409, response.text


@pytest.mark.contract
def test_post_roles_with_same_name_twice_returns_409() -> None:
    """Handler-derived stream_id from name means a second POST of the
    same name (case-insensitive) is a 409, not a fresh row. Prevents
    the projection-writer UNIQUE INDEX (LOWER(name)) race."""
    with TestClient(create_app()) as client:
        first = client.post("/roles", json=_body(name="Cartographer"))
        second = client.post("/roles", json=_body(name="cartographer"))
    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
