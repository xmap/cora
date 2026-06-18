"""Contract tests for `POST /methods/{method_id}/deprecate`.

Action endpoint, no body. Multi-source guard
(Defined | Versioned -> Deprecated). Mirrors
`test_deprecate_family_endpoint.py` (Equipment 5f-2).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def _define_method(client: TestClient, name: str = "XRF Mapping") -> UUID:
    """Seed a fresh Capability per call (each Method binds to its
    own Capability for test isolation)."""
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
def test_post_deprecate_method_returns_204_from_defined_state() -> None:
    """Direct deprecation (no prior versioning)."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(f"/methods/{method_id}/deprecate")
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_method_returns_204_from_versioned_state() -> None:
    """Full lifecycle: define + version + deprecate."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        client.post(f"/methods/{method_id}/version", json={"version_tag": "v1"})
        response = client.post(f"/methods/{method_id}/deprecate")
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_method_round_trips_into_get_method_response() -> None:
    """End-to-end: deprecate + get → status=Deprecated, version preserved."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        client.post(f"/methods/{method_id}/version", json={"version_tag": "2026-Q2"})
        client.post(f"/methods/{method_id}/deprecate")
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Deprecated"
    assert body["version"] == "2026-Q2"


@pytest.mark.contract
def test_post_deprecate_method_returns_404_when_method_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/methods/{missing_id}/deprecate")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_deprecate_method_returns_409_when_already_deprecated() -> None:
    """Strict-not-idempotent: re-deprecating raises 409."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        first = client.post(f"/methods/{method_id}/deprecate")
        assert first.status_code == 204
        second = client.post(f"/methods/{method_id}/deprecate")
    assert second.status_code == 409
    body = second.json()
    assert "Defined" in body["detail"]
    assert "Versioned" in body["detail"]


@pytest.mark.contract
def test_post_deprecate_method_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/methods/not-a-uuid/deprecate")
    assert response.status_code == 422
