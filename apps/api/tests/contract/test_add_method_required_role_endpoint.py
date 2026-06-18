"""Contract tests for `POST /methods/{method_id}/add-required-role`.

Action endpoint with body `{requirement: {role_name, family_id,
required_ports, optional}}`. Slice 1 of the positional role-tagging
workstream (IEC 81346 Function aspect). The sibling remove endpoint
contract lives in `test_remove_method_required_role_endpoint.py`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def _define_method(client: TestClient, name: str = "Tomography") -> UUID:
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


def _requirement_body(
    role_name: str = "detector",
    *,
    family_id: UUID | None = None,
) -> dict[str, object]:
    return {
        "role_name": role_name,
        "family_id": str(family_id or uuid4()),
        "required_ports": [
            {"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
        ],
        "optional": False,
    }


@pytest.mark.contract
def test_post_add_method_required_role_returns_201() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/add-required-role",
            json={"requirement": _requirement_body()},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_add_method_required_role_accepts_empty_required_ports() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        body = _requirement_body("axis")
        body["required_ports"] = []
        response = client.post(
            f"/methods/{method_id}/add-required-role",
            json={"requirement": body},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_add_method_required_role_returns_409_on_duplicate_role_name() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        body = _requirement_body("detector")
        first = client.post(
            f"/methods/{method_id}/add-required-role",
            json={"requirement": body},
        )
        assert first.status_code == 201
        second = client.post(
            f"/methods/{method_id}/add-required-role",
            json={"requirement": body},
        )
    assert second.status_code == 409
    assert "already has required role" in second.json()["detail"]


@pytest.mark.contract
def test_post_add_method_required_role_returns_404_for_unknown_method() -> None:
    unknown_id = uuid4()
    with TestClient(create_app()) as client:
        response = client.post(
            f"/methods/{unknown_id}/add-required-role",
            json={"requirement": _requirement_body()},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_method_required_role_returns_422_for_invalid_role_name_length() -> None:
    """Wire-layer Pydantic enforcement: role_name > 50 chars rejects at
    the boundary as 422 (schema-validation failure) before reaching
    the decider."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        body = _requirement_body("a" * 51)
        response = client.post(
            f"/methods/{method_id}/add-required-role",
            json={"requirement": body},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_method_required_role_returns_422_for_missing_required_fields() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/add-required-role",
            json={"requirement": {"role_name": "detector"}},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_method_required_role_returns_409_when_method_versioned() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        # Move to Versioned.
        versioned = client.post(
            f"/methods/{method_id}/version",
            json={"version_tag": "v1"},
        )
        assert versioned.status_code == 204, versioned.text
        response = client.post(
            f"/methods/{method_id}/add-required-role",
            json={"requirement": _requirement_body()},
        )
    assert response.status_code == 409
    assert "cannot mutate required roles" in response.json()["detail"]
