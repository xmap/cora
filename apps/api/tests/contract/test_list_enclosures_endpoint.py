"""Contract tests for `GET /enclosures`.

Pins the response shape + filter query-param wiring. The actual
projection-fold behavior is exercised by
`tests/integration/test_list_enclosures_handler_postgres.py`; this
file only exercises the route surface (status codes, schema,
authz wiring).
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_get_enclosures_returns_200_with_empty_items_when_no_data() -> None:
    """In-memory projection-less app returns an empty page (no pool wired)."""
    with TestClient(create_app()) as client:
        response = client.get("/enclosures")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


@pytest.mark.contract
def test_get_enclosures_accepts_facility_code_filter_with_empty_result() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/enclosures?facility_code=aps")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_enclosures_rejects_invalid_lifecycle_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/enclosures?lifecycle=Mystery")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_enclosures_rejects_invalid_permit_status_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/enclosures?permit_status=Mystery")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_enclosures_rejects_limit_above_100_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/enclosures?limit=101")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_enclosures_rejects_limit_below_1_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/enclosures?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_enclosures_accepts_full_filter_set() -> None:
    """All 3 filters provided at once should parse cleanly (returns empty list)."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/enclosures",
            params={
                "lifecycle": "Active",
                "permit_status": "Permitted",
                "facility_code": "aps",
                "limit": "25",
            },
        )
    assert response.status_code == 200
    assert response.json()["items"] == []
