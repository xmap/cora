"""Contract tests for `POST /assets/{id}/add-port` and `/remove-port`.

Combined file (mirror of test_condition_transitions consolidation)
since the two slices share a small contract surface.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(client: TestClient) -> str:
    response = client.post(
        "/assets",
        json={"name": "Detector-X", "tier": "Device", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["asset_id"]
    return asset_id


# ---------- add_port ----------


@pytest.mark.contract
def test_post_add_port_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-port",
            json={"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_add_port_returns_409_when_name_already_exists() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(
            f"/assets/{asset_id}/add-port",
            json={"port_name": "trigger", "direction": "Input", "signal_type": "TTL"},
        )
        assert first.status_code == 204
        # Same name (different direction + signal_type) — strict-not-idempotent.
        second = client.post(
            f"/assets/{asset_id}/add-port",
            json={"port_name": "trigger", "direction": "Output", "signal_type": "LVDS"},
        )
    assert second.status_code == 409
    assert "trigger" in second.json()["detail"]


@pytest.mark.contract
def test_post_add_port_returns_409_when_asset_decommissioned() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(
            f"/assets/{asset_id}/add-port",
            json={"port_name": "x", "direction": "Input", "signal_type": "TTL"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_add_port_returns_404_for_missing_asset() -> None:
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing}/add-port",
            json={"port_name": "x", "direction": "Input", "signal_type": "TTL"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_port_returns_422_for_missing_required_field() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-port",
            json={"port_name": "x", "direction": "Input"},  # missing signal_type
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_port_returns_422_for_invalid_direction_value() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-port",
            json={"port_name": "x", "direction": "Bidirectional", "signal_type": "TTL"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_port_returns_400_for_whitespace_only_name() -> None:
    """Pydantic min_length=1 catches "" but lets "   " through; the
    AssetPort VO then rejects with InvalidAssetPortNameError → 400."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-port",
            json={"port_name": "   ", "direction": "Input", "signal_type": "TTL"},
        )
    assert response.status_code == 400


# ---------- remove_port ----------


@pytest.mark.contract
def test_post_remove_port_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        client.post(
            f"/assets/{asset_id}/add-port",
            json={"port_name": "trigger", "direction": "Input", "signal_type": "TTL"},
        )
        response = client.post(
            f"/assets/{asset_id}/remove-port",
            json={"port_name": "trigger"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_remove_port_returns_409_when_port_not_found() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/remove-port",
            json={"port_name": "nonexistent"},
        )
    assert response.status_code == 409
    assert "nonexistent" in response.json()["detail"]


@pytest.mark.contract
def test_post_remove_port_returns_404_for_missing_asset() -> None:
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing}/remove-port",
            json={"port_name": "x"},
        )
    assert response.status_code == 404


# ---------- get_asset response shape ----------


@pytest.mark.contract
def test_get_asset_response_includes_ports_field() -> None:
    """5h side-effect: AssetResponse gains `ports: list`."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.get(f"/assets/{asset_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["ports"] == []


@pytest.mark.contract
def test_get_asset_response_lists_ports_sorted_by_name() -> None:
    """Round-trip: add several ports, get_asset returns them sorted."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        for name, direction, sig in [
            ("trigger_in", "Input", "TTL"),
            ("encoder_a", "Input", "Encoder"),
            ("sync_clock", "Output", "LVDS"),
        ]:
            r = client.post(
                f"/assets/{asset_id}/add-port",
                json={"port_name": name, "direction": direction, "signal_type": sig},
            )
            assert r.status_code == 204

        body = client.get(f"/assets/{asset_id}").json()

    # Sorted by name (encoder_a, sync_clock, trigger_in).
    assert [p["name"] for p in body["ports"]] == ["encoder_a", "sync_clock", "trigger_in"]
    assert body["ports"][0] == {"name": "encoder_a", "direction": "Input", "signal_type": "Encoder"}
