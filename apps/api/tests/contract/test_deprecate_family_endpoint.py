"""Contract tests for `POST /families/{family_id}/deprecate`.

Action endpoint, no body. Multi-source guard
(Defined | Versioned -> Deprecated).
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
def test_post_deprecate_family_returns_204_from_defined_state() -> None:
    """Direct deprecation (no prior versioning)."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(f"/families/{family_id}/deprecate", json={"reason": "Superseded"})
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_deprecate_family_returns_204_from_versioned_state() -> None:
    """Full lifecycle: define + version + deprecate."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        client.post(f"/families/{family_id}/version", json={"version_tag": "v1"})
        response = client.post(f"/families/{family_id}/deprecate", json={"reason": "Superseded"})
    assert response.status_code == 204


@pytest.mark.contract
def test_post_deprecate_family_round_trips_into_get_family_response() -> None:
    """End-to-end: deprecate + get → status=Deprecated, version preserved."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        client.post(
            f"/families/{family_id}/version",
            json={"version_tag": "2026-Q2", "affordances": []},
        )
        client.post(f"/families/{family_id}/deprecate", json={"reason": "Superseded"})
        response = client.get(f"/families/{family_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Deprecated"
    # Audit signal: latest version_tag preserved through deprecation.
    assert body["version"] == "2026-Q2"


@pytest.mark.contract
def test_post_deprecate_family_returns_404_when_capability_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/families/{missing_id}/deprecate", json={"reason": "Superseded"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_deprecate_family_returns_409_when_already_deprecated() -> None:
    """Strict-not-idempotent: re-deprecating raises 409."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        first = client.post(f"/families/{family_id}/deprecate", json={"reason": "Superseded"})
        assert first.status_code == 204
        second = client.post(f"/families/{family_id}/deprecate", json={"reason": "Superseded"})
    assert second.status_code == 409
    body = second.json()
    assert "Defined" in body["detail"]
    assert "Versioned" in body["detail"]


@pytest.mark.contract
def test_post_deprecate_family_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/families/not-a-uuid/deprecate", json={"reason": "Superseded"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_deprecate_missing_reason_returns_422() -> None:
    """`reason` is required: an empty body is a schema rejection."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(f"/families/{family_id}/deprecate", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_deprecate_unknown_reason_returns_422() -> None:
    """`reason` is a closed enum: prose is rejected at the schema."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            f"/families/{family_id}/deprecate", json={"reason": "superseded by a newer one"}
        )
    assert response.status_code == 422
