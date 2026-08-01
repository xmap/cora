"""Contract tests for `POST /practices/{practice_id}/deprecate`.

Mirror of `test_deprecate_method_endpoint.py`.
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
def test_post_deprecate_practice_returns_204_from_defined_state() -> None:
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        response = client.post(f"/practices/{practice_id}/deprecate", json={"reason": "Superseded"})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_practice_returns_204_from_versioned_state() -> None:
    """Full lifecycle: define + version + deprecate."""
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        client.post(f"/practices/{practice_id}/version", json={"version_tag": "v1"})
        response = client.post(f"/practices/{practice_id}/deprecate", json={"reason": "Superseded"})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_practice_round_trips_into_get_practice_response() -> None:
    """Audit signal: version preserved through deprecation."""
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        client.post(f"/practices/{practice_id}/version", json={"version_tag": "2026-Q2"})
        client.post(f"/practices/{practice_id}/deprecate", json={"reason": "Superseded"})
        response = client.get(f"/practices/{practice_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Deprecated"
    assert body["version"] == "2026-Q2"


@pytest.mark.contract
def test_post_deprecate_practice_returns_404_when_practice_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/practices/{missing_id}/deprecate", json={"reason": "Superseded"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_deprecate_practice_returns_409_when_already_deprecated() -> None:
    """Strict-not-idempotent."""
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        first = client.post(f"/practices/{practice_id}/deprecate", json={"reason": "Superseded"})
        assert first.status_code == 204
        second = client.post(f"/practices/{practice_id}/deprecate", json={"reason": "Superseded"})
    assert second.status_code == 409
    body = second.json()
    assert "Defined" in body["detail"]
    assert "Versioned" in body["detail"]


@pytest.mark.contract
def test_post_deprecate_practice_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/practices/not-a-uuid/deprecate", json={"reason": "Superseded"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_deprecate_missing_reason_returns_422() -> None:
    """`reason` is required: an empty body is a schema rejection."""
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        response = client.post(f"/practices/{practice_id}/deprecate", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_deprecate_unknown_reason_returns_422() -> None:
    """`reason` is a closed enum: prose is rejected at the schema."""
    with TestClient(create_app()) as client:
        practice_id = _define_practice(client)
        response = client.post(
            f"/practices/{practice_id}/deprecate", json={"reason": "superseded by a newer one"}
        )
    assert response.status_code == 422
