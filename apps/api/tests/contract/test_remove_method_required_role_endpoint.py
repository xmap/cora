"""Contract tests for `POST /methods/{method_id}/remove-required-role`.

Action endpoint with body `{role_name}`. Mirror of the add-side
contract; 204 No Content on success, strict-not-idempotent on
role_name.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def _define_method_with_role(
    client: TestClient,
    *,
    role_name: str = "detector",
) -> UUID:
    cap_id = create_capability_via_api(client)
    method_response = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "Tomography",
            "capability_id": cap_id,
            "needed_family_ids": [],
        },
    )
    assert method_response.status_code == 201, method_response.text
    method_id = UUID(method_response.json()["method_id"])
    add_response = client.post(
        f"/methods/{method_id}/add-required-role",
        json={
            "requirement": {
                "role_name": role_name,
                "family_id": str(uuid4()),
                "required_ports": [],
                "optional": False,
            }
        },
    )
    assert add_response.status_code == 201, add_response.text
    return method_id


@pytest.mark.contract
def test_post_remove_method_required_role_returns_204() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method_with_role(client)
        response = client.post(
            f"/methods/{method_id}/remove-required-role",
            json={"role_name": "detector"},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_remove_method_required_role_returns_404_for_unknown_role() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method_with_role(client)
        response = client.post(
            f"/methods/{method_id}/remove-required-role",
            json={"role_name": "sample_monitor"},
        )
    assert response.status_code == 404
    assert "does not have required role" in response.json()["detail"]


@pytest.mark.contract
def test_post_remove_method_required_role_returns_404_for_unknown_method() -> None:
    unknown_id = uuid4()
    with TestClient(create_app()) as client:
        response = client.post(
            f"/methods/{unknown_id}/remove-required-role",
            json={"role_name": "detector"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_remove_method_required_role_double_remove_is_strict_not_idempotent() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method_with_role(client)
        first = client.post(
            f"/methods/{method_id}/remove-required-role",
            json={"role_name": "detector"},
        )
        assert first.status_code == 204
        second = client.post(
            f"/methods/{method_id}/remove-required-role",
            json={"role_name": "detector"},
        )
    assert second.status_code == 404


@pytest.mark.contract
def test_post_remove_method_required_role_returns_422_for_invalid_role_name_length() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method_with_role(client)
        response = client.post(
            f"/methods/{method_id}/remove-required-role",
            json={"role_name": "a" * 51},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_remove_method_required_role_returns_409_when_method_versioned() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method_with_role(client)
        versioned = client.post(
            f"/methods/{method_id}/version",
            json={"version_tag": "v1"},
        )
        assert versioned.status_code == 204, versioned.text
        response = client.post(
            f"/methods/{method_id}/remove-required-role",
            json={"role_name": "detector"},
        )
    assert response.status_code == 409
