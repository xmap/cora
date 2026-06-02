"""Contract tests for `POST /assemblies/{assembly_id}/versions`.

Covers replace-on-version semantics, multi-source FSM (Defined and
Versioned both accept revisions), Deprecated rejection (deferred to
the deprecate_assembly slice landing; until then no Deprecated state
is reachable), AssemblyNotFound 404, and FamilyNotFound 404 on a
re-pointed presents_as_family_id.
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
    name: str = "MCTOptics",
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


@pytest.mark.contract
def test_post_assembly_version_returns_204_for_minimal_revision() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/versions",
            json={
                "name": "MCTOptics-rev2",
                "presents_as_family_id": str(family_id),
                "required_slots": [],
                "required_wires": [],
            },
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_assembly_version_allows_multiple_revisions_on_same_stream() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        for tag in ("v1", "v2", "v3"):
            response = client.post(
                f"/assemblies/{assembly_id}/versions",
                json={
                    "name": "MCTOptics",
                    "presents_as_family_id": str(family_id),
                    "required_slots": [],
                    "required_wires": [],
                    "version": tag,
                },
            )
            assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_assembly_version_allows_re_attestation_with_identical_body() -> None:
    """Re-attestation: posting the same body twice succeeds. Each call
    emits a fresh event capturing the audit moment."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        body: dict[str, object] = {
            "name": "MCTOptics",
            "presents_as_family_id": str(family_id),
            "required_slots": [],
            "required_wires": [],
            "version": "v1.0.0",
        }
        first = client.post(f"/assemblies/{assembly_id}/versions", json=body)
        assert first.status_code == 204, first.text
        second = client.post(f"/assemblies/{assembly_id}/versions", json=body)
    assert second.status_code == 204, second.text


@pytest.mark.contract
def test_post_assembly_version_returns_404_for_unknown_assembly() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            f"/assemblies/{uuid4()}/versions",
            json={
                "name": "X",
                "presents_as_family_id": str(family_id),
                "required_slots": [],
                "required_wires": [],
            },
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_assembly_version_returns_404_for_unknown_presents_as_family_id() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/versions",
            json={
                "name": "X",
                "presents_as_family_id": str(uuid4()),
                "required_slots": [],
                "required_wires": [],
            },
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_assembly_version_returns_400_when_wire_references_unknown_slot() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        camera_family = _define_family(client, "Camera")
        response = client.post(
            f"/assemblies/{assembly_id}/versions",
            json={
                "name": "X",
                "presents_as_family_id": str(family_id),
                "required_slots": [
                    {
                        "slot_name": "camera",
                        "required_families": [str(camera_family)],
                        "cardinality": "Exactly1",
                    }
                ],
                "required_wires": [
                    {
                        "source_slot_name": "missing_slot",
                        "source_port_name": "out",
                        "target_slot_name": "camera",
                        "target_port_name": "in",
                    }
                ],
            },
        )
    assert response.status_code == 400, response.text
    assert "missing_slot" in response.json()["detail"]


@pytest.mark.contract
def test_post_assembly_version_returns_400_for_invalid_parameter_overrides_schema() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/versions",
            json={
                "name": "X",
                "presents_as_family_id": str(family_id),
                "required_slots": [],
                "required_wires": [],
                "parameter_overrides_schema": {"oneOf": [{"type": "object"}]},
            },
        )
    assert response.status_code == 400, response.text


@pytest.mark.contract
def test_post_assembly_version_returns_422_for_missing_name() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        response = client.post(
            f"/assemblies/{assembly_id}/versions",
            json={"presents_as_family_id": str(family_id)},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assembly_version_replaces_structural_fields() -> None:
    """Replace-on-version: new slot set wholesale replaces the old."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        assembly_id = _define_assembly(client, family_id)
        camera_family = _define_family(client, "Camera")
        scintillator_family = _define_family(client, "Scintillator")
        response = client.post(
            f"/assemblies/{assembly_id}/versions",
            json={
                "name": "Detector",
                "presents_as_family_id": str(family_id),
                "required_slots": [
                    {
                        "slot_name": "camera",
                        "required_families": [str(camera_family)],
                        "cardinality": "Exactly1",
                    },
                    {
                        "slot_name": "scintillator",
                        "required_families": [str(scintillator_family)],
                        "cardinality": "Exactly1",
                    },
                ],
                "required_wires": [],
                "version": "v0.2.0",
            },
        )
    assert response.status_code == 204, response.text
