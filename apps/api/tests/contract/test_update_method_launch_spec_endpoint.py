"""Contract tests for `POST /methods/{method_id}/launch-spec`.

Action endpoint with body `{launch_spec}` (or null to clear). The spec's
args are cross-checked against the Method's parameters_schema, so the
setup sets a schema first. In-process app + in-memory stores (no DB).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _method_with_schema(client: TestClient) -> UUID:
    """Define a Method and set a parameters_schema with num_iter + remove_stripe."""
    cap_id = create_capability_via_api(client)
    method_id = UUID(
        client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "recon",
                "capability_id": cap_id,
                "needed_family_ids": [],
            },
        ).json()["method_id"]
    )
    schema: dict[str, Any] = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "num_iter": {"type": "integer", "minimum": 1},
            "remove_stripe": {"type": "boolean"},
        },
    }
    resp = client.post(
        f"/methods/{method_id}/parameters-schema", json={"parameters_schema": schema}
    )
    assert resp.status_code == 204, resp.text
    return method_id


def _valid_launch_spec() -> dict[str, Any]:
    return {
        "base_command": ["tomopy", "recon"],
        "args": [
            {"name": "num_iter", "flag": "--num-iter", "required": True},
            {"name": "remove_stripe", "flag": "--remove-stripe", "style": "flag_only"},
        ],
        "input_arg": "--input",
        "output_arg": "--output",
    }


@pytest.mark.contract
def test_post_update_method_launch_spec_returns_204_when_setting_valid_spec() -> None:
    with TestClient(create_app()) as client:
        method_id = _method_with_schema(client)
        response = client.post(
            f"/methods/{method_id}/launch-spec",
            json={"launch_spec": _valid_launch_spec()},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_update_method_launch_spec_returns_204_when_clearing() -> None:
    with TestClient(create_app()) as client:
        method_id = _method_with_schema(client)
        client.post(f"/methods/{method_id}/launch-spec", json={"launch_spec": _valid_launch_spec()})
        cleared = client.post(f"/methods/{method_id}/launch-spec", json={"launch_spec": None})
    assert cleared.status_code == 204


@pytest.mark.contract
def test_post_update_method_launch_spec_returns_400_for_unknown_parameter() -> None:
    with TestClient(create_app()) as client:
        method_id = _method_with_schema(client)
        response = client.post(
            f"/methods/{method_id}/launch-spec",
            json={
                "launch_spec": {
                    "base_command": ["x"],
                    "args": [{"name": "not_a_key", "flag": "--nope"}],
                }
            },
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_update_method_launch_spec_returns_400_for_flag_only_on_non_boolean() -> None:
    with TestClient(create_app()) as client:
        method_id = _method_with_schema(client)
        response = client.post(
            f"/methods/{method_id}/launch-spec",
            json={
                "launch_spec": {
                    "base_command": ["x"],
                    "args": [{"name": "num_iter", "flag": "--n", "style": "flag_only"}],
                }
            },
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_update_method_launch_spec_returns_404_for_unknown_method() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/methods/{uuid4()}/launch-spec",
            json={"launch_spec": {"base_command": ["x"], "args": []}},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_update_method_launch_spec_returns_422_for_malformed_body() -> None:
    """Empty base_command fails Pydantic min_length before the handler."""
    with TestClient(create_app()) as client:
        method_id = _method_with_schema(client)
        response = client.post(
            f"/methods/{method_id}/launch-spec",
            json={"launch_spec": {"base_command": [], "args": []}},
        )
    assert response.status_code == 422
