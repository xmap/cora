"""Contract tests for `POST /methods/{method_id}/version`.

Action endpoint with body `{version_tag}`. Multi-source guard
(Defined | Versioned -> Versioned). Mirrors
`test_version_family_endpoint.py` (Equipment 5f-2).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


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
    assert response.status_code == 201
    return UUID(response.json()["method_id"])


@pytest.mark.contract
def test_post_version_method_returns_204_from_defined_state() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/version",
            json={"version_tag": "v2"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_version_method_returns_204_from_versioned_state() -> None:
    """Subsequent revision (Versioned → Versioned)."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        first = client.post(f"/methods/{method_id}/version", json={"version_tag": "v1"})
        assert first.status_code == 204
        second = client.post(f"/methods/{method_id}/version", json={"version_tag": "v2"})
    assert second.status_code == 204


@pytest.mark.contract
def test_post_version_method_round_trips_into_get_method_response() -> None:
    """End-to-end: version + get → status=Versioned, version=label."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        client.post(f"/methods/{method_id}/version", json={"version_tag": "2026-Q3"})
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Versioned"
    assert body["version"] == "2026-Q3"


@pytest.mark.contract
def test_post_version_method_returns_404_when_method_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/methods/{missing_id}/version", json={"version_tag": "v1"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_version_method_returns_409_when_deprecated() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        deprecate = client.post(f"/methods/{method_id}/deprecate")
        assert deprecate.status_code == 204
        response = client.post(f"/methods/{method_id}/version", json={"version_tag": "v2"})
    assert response.status_code == 409
    assert "Deprecated" in response.json()["detail"]


@pytest.mark.contract
def test_post_version_method_rejects_empty_version_tag_with_422() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(f"/methods/{method_id}/version", json={"version_tag": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_method_rejects_whitespace_only_with_400() -> None:
    """Whitespace passes Pydantic but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(f"/methods/{method_id}/version", json={"version_tag": "   "})
    assert response.status_code == 400
    assert "version tag" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_version_method_rejects_too_long_with_422() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(f"/methods/{method_id}/version", json={"version_tag": "v" * 51})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_method_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/methods/not-a-uuid/version", json={"version_tag": "v1"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_method_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/version",
            json={"version_tag": "v1"},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
