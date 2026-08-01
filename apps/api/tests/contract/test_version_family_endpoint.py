"""Contract tests for `POST /families/{family_id}/version`.

Action endpoint with body `{version_tag}`. Multi-source guard
(Defined | Versioned -> Versioned).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_family(client: TestClient, name: str = "Tomography") -> UUID:
    response = client.post("/families", json={"name": name, "affordances": []})
    assert response.status_code == 201
    return UUID(response.json()["family_id"])


@pytest.mark.contract
def test_post_version_family_returns_204_from_defined_state() -> None:
    """First revision (Defined → Versioned)."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            f"/families/{family_id}/version",
            json={"version_tag": "v2", "affordances": []},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_version_family_returns_204_from_versioned_state() -> None:
    """Subsequent revision (Versioned → Versioned)."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        first = client.post(
            f"/families/{family_id}/version", json={"version_tag": "v1", "affordances": []}
        )
        assert first.status_code == 204
        second = client.post(
            f"/families/{family_id}/version", json={"version_tag": "v2", "affordances": []}
        )
    assert second.status_code == 204


@pytest.mark.contract
def test_post_version_family_round_trips_into_get_family_response() -> None:
    """End-to-end: version + get → status=Versioned, version=label."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        client.post(
            f"/families/{family_id}/version",
            json={"version_tag": "2026-Q3", "affordances": []},
        )
        response = client.get(f"/families/{family_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Versioned"
    assert body["version"] == "2026-Q3"


@pytest.mark.contract
def test_post_version_family_returns_404_when_capability_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/families/{missing_id}/version", json={"version_tag": "v1", "affordances": []}
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_version_family_returns_409_when_deprecated() -> None:
    """Deprecated capabilities cannot be re-versioned."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        deprecate = client.post(f"/families/{family_id}/deprecate", json={"reason": "Superseded"})
        assert deprecate.status_code == 204
        response = client.post(
            f"/families/{family_id}/version", json={"version_tag": "v2", "affordances": []}
        )
    assert response.status_code == 409
    assert "Deprecated" in response.json()["detail"]


@pytest.mark.contract
def test_post_version_family_rejects_empty_version_tag_with_422() -> None:
    """Pydantic min_length=1 catches empty strings before the domain layer."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            f"/families/{family_id}/version", json={"version_tag": "", "affordances": []}
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_family_rejects_whitespace_only_with_400() -> None:
    """Whitespace passes Pydantic but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            f"/families/{family_id}/version",
            json={"version_tag": "   ", "affordances": []},
        )
    assert response.status_code == 400
    assert "version tag" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_version_family_rejects_too_long_with_422() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            f"/families/{family_id}/version",
            json={"version_tag": "v" * 51},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_family_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/families/not-a-uuid/version", json={"version_tag": "v1", "affordances": []}
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_family_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            f"/families/{family_id}/version",
            json={"version_tag": "v1", "affordances": []},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
