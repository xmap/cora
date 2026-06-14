"""Contract tests for `POST /assemblies/{assembly_id}/deprecate`.

Covers multi-source FSM (Defined and Versioned both accept the
deprecate command), strict-not-idempotent re-deprecate, 404 on
unknown assembly, 422 on missing reason.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_family(client: TestClient, name: str = "Detector") -> UUID:
    response = client.post(
        "/families",
        json={"name": name, "affordances": []},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["family_id"])


def _define_assembly(
    client: TestClient,
    family_id: UUID,
    *,
    name: str = "Microscope",
) -> UUID:
    response = client.post(
        "/assemblies",
        json={
            "name": name,
            "presents_as_family_id": str(family_id),
            "required_slots": [],
            "required_wires": [],
        },
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["assembly_id"])


def _version_assembly(client: TestClient, assembly_id: UUID, family_id: UUID) -> None:
    response = client.post(
        f"/assemblies/{assembly_id}/versions",
        json={
            "name": "Microscope",
            "presents_as_family_id": str(family_id),
            "required_slots": [],
            "required_wires": [],
            "version": "v1",
        },
    )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_assembly_deprecate_returns_204_for_defined_state() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/deprecate",
            json={"reason": "superseded"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_assembly_deprecate_returns_204_for_versioned_state() -> None:
    """Multi-source FSM: Versioned -> Deprecated is accepted."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        _version_assembly(client, assembly_id, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/deprecate",
            json={"reason": "end-of-life"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_assembly_deprecate_returns_404_for_unknown_assembly() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assemblies/{uuid4()}/deprecate",
            json={"reason": "r"},
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_assembly_deprecate_returns_409_for_already_deprecated() -> None:
    """Strict-not-idempotent: re-deprecate raises 409."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        first = client.post(
            f"/assemblies/{assembly_id}/deprecate",
            json={"reason": "first"},
        )
        assert first.status_code == 204, first.text
        second = client.post(
            f"/assemblies/{assembly_id}/deprecate",
            json={"reason": "second"},
        )
    assert second.status_code == 409, second.text
    assert "Deprecated" in second.json()["detail"]


@pytest.mark.contract
def test_post_assembly_deprecate_returns_422_for_missing_reason() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        response = client.post(f"/assemblies/{assembly_id}/deprecate", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assembly_deprecate_returns_422_for_empty_reason() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/deprecate",
            json={"reason": ""},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assembly_deprecate_blocks_subsequent_version() -> None:
    """Once Deprecated, version_assembly rejects with 409."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        deprecate_response = client.post(
            f"/assemblies/{assembly_id}/deprecate",
            json={"reason": "superseded"},
        )
        assert deprecate_response.status_code == 204, deprecate_response.text
        version_response = client.post(
            f"/assemblies/{assembly_id}/versions",
            json={
                "name": "Microscope",
                "presents_as_family_id": str(family_id),
                "required_slots": [],
                "required_wires": [],
                "version": "v9",
            },
        )
    assert version_response.status_code == 409, version_response.text
