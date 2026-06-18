"""Contract tests for `GET /methods/{method_id}`.

Mirrors `test_get_family_endpoint.py`. Pinned response shape:
`{id, name, needed_family_ids, status}`. needed_family_ids is a
sorted list of UUIDs (deterministic ordering).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def _define_method(
    client: TestClient,
    *,
    name: str = "XRF Mapping",
    needed_family_ids: list[str] | None = None,
    needed_supplies: list[str] | None = None,
    execution_pattern: str = "Batch",
    monotone_quality: bool = False,
    resumable_from_checkpoint: bool = False,
) -> UUID:
    body: dict[str, object] = {
        "execution_pattern": execution_pattern,
        "name": name,
        # Capability per call so tests stay isolated.
        "capability_id": create_capability_via_api(client),
        "needed_family_ids": needed_family_ids if needed_family_ids is not None else [],
        "monotone_quality": monotone_quality,
        "resumable_from_checkpoint": resumable_from_checkpoint,
    }
    if needed_supplies is not None:
        body["needed_supplies"] = needed_supplies
    response = client.post("/methods", json=body)
    assert response.status_code == 201, response.text
    return UUID(response.json()["method_id"])


@pytest.mark.contract
def test_get_method_returns_200_with_defined_status_for_new_method() -> None:
    cap1 = str(uuid4())
    cap2 = str(uuid4())
    with TestClient(create_app()) as client:
        method_id = _define_method(
            client,
            name="XRF Fly Mapping",
            needed_family_ids=[cap1, cap2],
        )
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(method_id)
    assert body["name"] == "XRF Fly Mapping"
    assert body["status"] == "Defined"
    # Sorted by UUID string form (deterministic).
    assert body["needed_family_ids"] == sorted([cap1, cap2])
    # Null until version_method runs (6b).
    assert body["version"] is None


@pytest.mark.contract
def test_get_method_returns_empty_needed_family_ids_for_procedural_method() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client, name="Sample Cleaning", needed_family_ids=[])
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["needed_family_ids"] == []


# ---------- needed_supplies on response ----------


@pytest.mark.contract
def test_get_method_returns_needed_supplies_sorted_lexically() -> None:
    """Method.needed_supplies surfaces on the GET response as a
    sorted list of Supply.kind strings."""
    with TestClient(create_app()) as client:
        method_id = _define_method(
            client,
            name="Tomography",
            needed_supplies=["PhotonBeam", "LiquidNitrogen"],
        )
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    # Sorted lexically (deterministic ordering, mirrors needed_family_ids convention).
    assert body["needed_supplies"] == ["LiquidNitrogen", "PhotonBeam"]


@pytest.mark.contract
def test_get_method_returns_empty_needed_supplies_when_unspecified() -> None:
    """Backward-compat: omit needed_supplies in POST body, response
    still includes the field as []. Pre-10b clients keep working."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client, name="X", needed_family_ids=[])
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["needed_supplies"] == []


@pytest.mark.contract
def test_define_method_returns_422_for_oversized_supply_kind() -> None:
    """Pydantic per-element max_length=50 catches at the boundary."""
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "X",
                "capability_id": _cap_id,
                "needed_family_ids": [],
                "needed_supplies": ["x" * 51],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_define_method_returns_422_for_empty_supply_kind() -> None:
    """Pydantic per-element min_length=1 catches at the boundary."""
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        response = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "X",
                "capability_id": _cap_id,
                "needed_family_ids": [],
                "needed_supplies": [""],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_get_method_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/methods/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_method_returns_422_for_malformed_method_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/methods/not-a-uuid")
    assert response.status_code == 422


# ---------- compute classification on response ----------


@pytest.mark.contract
def test_get_method_returns_compute_classification_defaults_for_batch() -> None:
    """A Batch Method surfaces execution_pattern="Batch" and the two
    claims default to False on the GET response."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client, name="Gridrec", needed_family_ids=[])
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["execution_pattern"] == "Batch"
    assert body["monotone_quality"] is False
    assert body["resumable_from_checkpoint"] is False


@pytest.mark.contract
def test_get_method_round_trips_iterative_compute_classification() -> None:
    """An Iterative Method with both claims set round-trips through the
    GET response (define -> get)."""
    with TestClient(create_app()) as client:
        method_id = _define_method(
            client,
            name="SIRT",
            needed_family_ids=[],
            execution_pattern="Iterative",
            monotone_quality=True,
            resumable_from_checkpoint=True,
        )
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["execution_pattern"] == "Iterative"
    assert body["monotone_quality"] is True
    assert body["resumable_from_checkpoint"] is True


# ---------- Lifecycle timestamps in response ----------


@pytest.mark.contract
def test_get_method_response_includes_lifecycle_timestamp_fields() -> None:
    """Path C: response surfaces `created_at` / `versioned_at` /
    `deprecated_at` keys regardless of whether the projection has
    folded yet. Under the in-memory contract harness the values are
    null because no projection runs; the postgres integration suite
    pins the populated path."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client, name="X", needed_family_ids=[])
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert "created_at" in body
    assert "versioned_at" in body
    assert "deprecated_at" in body
    # In-memory harness: no projection runs, so all three are null.
    assert body["created_at"] is None
    assert body["versioned_at"] is None
    assert body["deprecated_at"] is None
