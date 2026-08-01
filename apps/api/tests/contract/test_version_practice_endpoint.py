"""Contract tests for `POST /practices/{practice_id}/version`.

Mirror of `test_version_method_endpoint.py`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_practice(client: TestClient) -> UUID:
    response = client.post(
        "/practices",
        json={
            "name": "APS Standard Tomography",
            "method_id": str(uuid4()),
            "site_id": str(uuid4()),
        },
    )
    assert response.status_code == 201
    return UUID(response.json()["practice_id"])


@pytest.mark.contract
def test_post_version_practice_returns_204_from_defined_state() -> None:
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        response = client.post(f"/practices/{practice_id}/version", json={"version_tag": "v2"})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_version_practice_returns_204_from_versioned_state() -> None:
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        first = client.post(f"/practices/{practice_id}/version", json={"version_tag": "v1"})
        assert first.status_code == 204
        second = client.post(f"/practices/{practice_id}/version", json={"version_tag": "v2"})
    assert second.status_code == 204


@pytest.mark.contract
def test_post_version_practice_round_trips_into_get_practice_response() -> None:
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        client.post(f"/practices/{practice_id}/version", json={"version_tag": "2026-Q3"})
        response = client.get(f"/practices/{practice_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Versioned"
    assert body["version"] == "2026-Q3"


@pytest.mark.contract
def test_post_version_practice_returns_404_when_practice_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/practices/{missing_id}/version", json={"version_tag": "v1"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_version_practice_returns_409_when_deprecated() -> None:
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        deprecate = client.post(
            f"/practices/{practice_id}/deprecate", json={"reason": "Superseded"}
        )
        assert deprecate.status_code == 204
        response = client.post(f"/practices/{practice_id}/version", json={"version_tag": "v2"})
    assert response.status_code == 409
    assert "Deprecated" in response.json()["detail"]


@pytest.mark.contract
def test_post_version_practice_rejects_empty_version_tag_with_422() -> None:
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        response = client.post(f"/practices/{practice_id}/version", json={"version_tag": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_practice_rejects_whitespace_only_with_400() -> None:
    """Whitespace passes Pydantic but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        response = client.post(f"/practices/{practice_id}/version", json={"version_tag": "   "})
    assert response.status_code == 400
    assert "version tag" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_version_practice_rejects_too_long_with_422() -> None:
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        response = client.post(f"/practices/{practice_id}/version", json={"version_tag": "v" * 51})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_practice_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/practices/not-a-uuid/version", json={"version_tag": "v1"})
    assert response.status_code == 422
