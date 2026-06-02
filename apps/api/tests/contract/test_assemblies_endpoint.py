"""Contract tests for `POST /assemblies`.

Covers the create-style basics (request schema, response schema,
status codes), the structural validation at the API boundary
(missing required fields, malformed wire, invalid cardinality,
unknown-slot wire endpoint), and the FamilyNotFound 404 path via
the in-memory event store.

Assembly is the 5th Equipment aggregate; per the design memo's
gate-review discipline, contract tests ship with the slice (no
EXEMPT_FROM_*_CONTRACT allowlist entry).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.assembly import ASSEMBLY_NAME_MAX_LENGTH


def _define_family(client: TestClient, name: str = "Camera") -> UUID:
    """Define a Family and return its id. Used to seed presents_as_family_id."""
    response = client.post(
        "/families",
        json={"name": name, "affordances": []},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["family_id"])


@pytest.mark.contract
def test_post_assemblies_returns_201_with_assembly_id_for_minimal_body() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            "/assemblies",
            json={
                "name": "Detector",
                "presents_as_family_id": str(family_id),
                "required_slots": [],
                "required_wires": [],
            },
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "assembly_id" in body
    UUID(body["assembly_id"])


@pytest.mark.contract
def test_post_assemblies_returns_201_with_slots_and_wires() -> None:
    with TestClient(create_app()) as client:
        presents_id = _define_family(client, "Detector")
        camera_family = _define_family(client, "Camera")
        trigger_family = _define_family(client, "TriggerSource")
        response = client.post(
            "/assemblies",
            json={
                "name": "MCTOptics",
                "presents_as_family_id": str(presents_id),
                "required_slots": [
                    {
                        "slot_name": "camera",
                        "required_family_ids": [str(camera_family)],
                        "cardinality": "Exactly1",
                    },
                    {
                        "slot_name": "trigger_source",
                        "required_family_ids": [str(trigger_family)],
                        "cardinality": "Exactly1",
                    },
                ],
                "required_wires": [
                    {
                        "source_slot_name": "trigger_source",
                        "source_port_name": "trigger_out",
                        "target_slot_name": "camera",
                        "target_port_name": "trigger_in",
                    }
                ],
            },
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_assemblies_returns_404_for_unknown_presents_as_family_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assemblies",
            json={
                "name": "Detector",
                "presents_as_family_id": str(uuid4()),
                "required_slots": [],
                "required_wires": [],
            },
        )
    assert response.status_code == 404, response.text
    assert "Family" in response.json()["detail"]


@pytest.mark.contract
def test_post_assemblies_returns_404_when_slot_required_family_missing() -> None:
    with TestClient(create_app()) as client:
        presents_id = _define_family(client, "Detector")
        response = client.post(
            "/assemblies",
            json={
                "name": "Detector",
                "presents_as_family_id": str(presents_id),
                "required_slots": [
                    {
                        "slot_name": "camera",
                        "required_family_ids": [str(uuid4())],
                        "cardinality": "Exactly1",
                    }
                ],
                "required_wires": [],
            },
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_assemblies_returns_400_for_invalid_parameter_overrides_schema() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            "/assemblies",
            json={
                "name": "Detector",
                "presents_as_family_id": str(family_id),
                "required_slots": [],
                "required_wires": [],
                "parameter_overrides_schema": {"oneOf": [{"type": "object"}]},
            },
        )
    assert response.status_code == 400, response.text
    assert "parameter_overrides_schema" in response.json()["detail"]


@pytest.mark.contract
def test_post_assemblies_returns_400_when_wire_references_unknown_slot() -> None:
    with TestClient(create_app()) as client:
        presents_id = _define_family(client, "Detector")
        camera_family = _define_family(client, "Camera")
        response = client.post(
            "/assemblies",
            json={
                "name": "Detector",
                "presents_as_family_id": str(presents_id),
                "required_slots": [
                    {
                        "slot_name": "camera",
                        "required_family_ids": [str(camera_family)],
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
def test_post_assemblies_returns_400_for_degenerate_full_self_loop_wire() -> None:
    with TestClient(create_app()) as client:
        presents_id = _define_family(client, "Detector")
        lut_family = _define_family(client, "Lut")
        response = client.post(
            "/assemblies",
            json={
                "name": "X",
                "presents_as_family_id": str(presents_id),
                "required_slots": [
                    {
                        "slot_name": "lut",
                        "required_family_ids": [str(lut_family)],
                        "cardinality": "Exactly1",
                    }
                ],
                "required_wires": [
                    {
                        "source_slot_name": "lut",
                        "source_port_name": "out",
                        "target_slot_name": "lut",
                        "target_port_name": "out",
                    }
                ],
            },
        )
    assert response.status_code == 400, response.text
    assert "degenerate" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_assemblies_returns_422_for_missing_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assemblies",
            json={"presents_as_family_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assemblies_returns_422_for_name_too_long() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assemblies",
            json={
                "name": "x" * (ASSEMBLY_NAME_MAX_LENGTH + 1),
                "presents_as_family_id": str(uuid4()),
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assemblies_returns_422_for_unknown_cardinality() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            "/assemblies",
            json={
                "name": "X",
                "presents_as_family_id": str(family_id),
                "required_slots": [
                    {
                        "slot_name": "camera",
                        "required_family_ids": [str(family_id)],
                        "cardinality": "Bogus",
                    }
                ],
                "required_wires": [],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assemblies_returns_422_for_empty_required_family_ids() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            "/assemblies",
            json={
                "name": "X",
                "presents_as_family_id": str(family_id),
                "required_slots": [
                    {
                        "slot_name": "orphan",
                        "required_family_ids": [],
                        "cardinality": "ZeroOrMore",
                    }
                ],
                "required_wires": [],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assemblies_idempotency_key_returns_same_assembly_id() -> None:
    """Idempotency-Key replay returns the original assembly_id."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        body: dict[str, object] = {
            "name": "Idempotent",
            "presents_as_family_id": str(family_id),
            "required_slots": [],
            "required_wires": [],
        }
        headers = {"Idempotency-Key": "test-key-12345"}
        first = client.post("/assemblies", json=body, headers=headers)
        assert first.status_code == 201, first.text
        second = client.post("/assemblies", json=body, headers=headers)
    assert second.status_code in (200, 201)
    assert first.json()["assembly_id"] == second.json()["assembly_id"]


@pytest.mark.contract
def test_post_assemblies_response_omits_content_hash() -> None:
    """The POST /assemblies response carries only assembly_id; content_hash
    is on the event payload and surfaces via list_assemblies / get_assembly
    when those slices ship."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        response = client.post(
            "/assemblies",
            json={
                "name": "X",
                "presents_as_family_id": str(family_id),
                "required_slots": [],
                "required_wires": [],
            },
        )
    assert response.status_code == 201
    assert response.json().keys() == {"assembly_id"}
