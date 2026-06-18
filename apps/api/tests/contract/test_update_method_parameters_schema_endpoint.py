"""Contract tests for `POST /methods/{method_id}/parameters-schema`.

Action endpoint with body `{parameters_schema}`. Schema
can be set, replaced, or cleared (null payload). Mirrors
`test_update_family_settings_schema_endpoint.py`.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _define_method(client: TestClient, name: str = "XRF Mapping") -> UUID:
    """Seed a fresh Capability per call."""
    cap_id = create_capability_via_api(client)
    response = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": name,
            "capability_id": cap_id,
            "needed_family_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["method_id"])


def _example_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            },
        },
        "required": ["energy"],
    }


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_204_when_setting_schema() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": _example_schema()},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_204_when_clearing_schema() -> None:
    """Pass null to clear a previously-set schema."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        first = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": _example_schema()},
        )
        assert first.status_code == 204
        cleared = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": None},
        )
    assert cleared.status_code == 204


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_400_for_missing_dollar_schema() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": {"type": "object"}},  # missing $schema
        )
    assert response.status_code == 400
    body = response.json()
    assert "Invalid Method parameters_schema" in body["detail"]


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_400_for_forbidden_keyword() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={
                "parameters_schema": {
                    "$schema": _DRAFT,
                    "oneOf": [{"type": "string"}, {"type": "integer"}],
                },
            },
        )
    assert response.status_code == 400
    body = response.json()
    assert "forbidden keyword" in body["detail"]


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_404_for_unknown_method() -> None:
    unknown_id = uuid4()
    with TestClient(create_app()) as client:
        response = client.post(
            f"/methods/{unknown_id}/parameters-schema",
            json={"parameters_schema": _example_schema()},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_422_for_malformed_path() -> None:
    """Bad UUID in path -> Pydantic 422."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods/not-a-uuid/parameters-schema",
            json={"parameters_schema": None},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_update_method_parameters_schema_iterative_without_stopping_key_returns_400() -> None:
    """L4(a) end-to-end: an Iterative Method whose schema declares no
    max_iter-shape or tol-shape stopping key is rejected with 400 via
    the Invalid<X> validation handler (parity with the L4(b) 400 test
    on POST /methods)."""
    with TestClient(create_app()) as client:
        cap_id = create_capability_via_api(client)
        method_id = UUID(
            client.post(
                "/methods",
                json={
                    "execution_pattern": "Iterative",
                    "name": "SIRT",
                    "capability_id": cap_id,
                    "needed_family_ids": [],
                },
            ).json()["method_id"]
        )
        response = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={
                "parameters_schema": {
                    "$schema": _DRAFT,
                    "type": "object",
                    "properties": {"energy": {"type": "number"}},
                }
            },
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_update_method_parameters_schema_iterative_with_stopping_key_returns_204() -> None:
    """An Iterative Method whose schema declares a budget stopping key
    (num_iter) satisfies L4(a) and the update succeeds (204)."""
    with TestClient(create_app()) as client:
        cap_id = create_capability_via_api(client)
        method_id = UUID(
            client.post(
                "/methods",
                json={
                    "execution_pattern": "Iterative",
                    "name": "SIRT",
                    "capability_id": cap_id,
                    "needed_family_ids": [],
                },
            ).json()["method_id"]
        )
        response = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={
                "parameters_schema": {
                    "$schema": _DRAFT,
                    "type": "object",
                    "properties": {"num_iter": {"type": "integer"}},
                }
            },
        )
    assert response.status_code == 204
