"""Contract tests for `GET /enclosures/{enclosure_id}/history`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _setup_enclosure(client: TestClient) -> str:
    return client.post(
        "/enclosures",
        json={"name": "2-BM-A", "facility_code": "cora"},
    ).json()["enclosure_id"]


@pytest.mark.contract
def test_get_enclosure_history_returns_200_with_registered_event() -> None:
    with TestClient(create_app()) as client:
        enclosure_id = _setup_enclosure(client)
        response = client.get(f"/enclosures/{enclosure_id}/history")

    assert response.status_code == 200
    body = response.json()
    assert body["enclosure_id"] == enclosure_id
    assert body["name"] == "2-BM-A"
    assert body["permit_status"] == "Unknown"
    assert body["lifecycle"] == "Active"
    assert len(body["events"]) == 1
    assert body["events"][0]["event_type"] == "EnclosureRegistered"
    assert body["events_truncated"] is False


@pytest.mark.contract
def test_get_enclosure_history_reflects_decommission() -> None:
    with TestClient(create_app()) as client:
        enclosure_id = _setup_enclosure(client)
        client.post(f"/enclosures/{enclosure_id}/decommission", json={"reason": "test"})
        response = client.get(f"/enclosures/{enclosure_id}/history")

    body = response.json()
    assert body["lifecycle"] == "Decommissioned"
    assert [e["event_type"] for e in body["events"]] == [
        "EnclosureRegistered",
        "EnclosureDecommissioned",
    ]


@pytest.mark.contract
def test_get_enclosure_history_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/enclosures/{uuid4()}/history")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_enclosure_history_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/enclosures/not-a-uuid/history")
    assert response.status_code == 422
