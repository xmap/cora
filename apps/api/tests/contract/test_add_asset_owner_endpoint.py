"""Contract tests for `POST /assets/{id}/add-owner`."""

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


@pytest.mark.contract
def test_add_asset_owner_route_201_on_success() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-owner",
            json={"owner": {"name": "HZB"}},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_add_asset_owner_route_409_when_name_already_present() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(
            f"/assets/{asset_id}/add-owner",
            json={"owner": {"name": "HZB"}},
        )
        assert first.status_code == 201
        second = client.post(
            f"/assets/{asset_id}/add-owner",
            json={"owner": {"name": "HZB", "contact": "ops@hzb.de"}},
        )
    assert second.status_code == 409
    assert "HZB" in second.json()["detail"]


@pytest.mark.contract
def test_add_asset_owner_route_409_when_decommissioned() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(
            f"/assets/{asset_id}/add-owner",
            json={"owner": {"name": "HZB"}},
        )
    assert response.status_code == 409
    assert "Decommissioned" in response.json()["detail"]


@pytest.mark.contract
def test_add_asset_owner_route_422_when_required_field_missing() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-owner",
            json={"owner": {}},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_add_asset_owner_route_400_on_invalid_pairing() -> None:
    """Pydantic accepts identifier without identifier_type (each field
    is optional in isolation); the AssetOwner VO's __post_init__
    enforces the pairing invariant and raises
    `InvalidAssetOwnerIdentifierPairingError` (400)."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-owner",
            json={
                "owner": {
                    "name": "HZB",
                    "identifier": "02aj13c28",
                    # identifier_type intentionally omitted
                }
            },
        )
    assert response.status_code == 400
    assert "both set or both None" in response.json()["detail"]


@pytest.mark.contract
def test_add_asset_owner_route_404_when_asset_not_found() -> None:
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing}/add-owner",
            json={"owner": {"name": "HZB"}},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_register_asset_route_accepts_owners_field() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={
                "name": "Detector-X",
                "tier": "Device",
                "parent_id": str(uuid4()),
                "owners": [
                    {
                        "name": "Helmholtz-Zentrum Berlin",
                        "contact": "instrument-data@helmholtz-berlin.de",
                        "identifier": "https://ror.org/02aj13c28",
                        "identifier_type": "ROR",
                    }
                ],
            },
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_register_asset_route_owners_field_optional() -> None:
    """Legacy callers omitting the new owners field still succeed
    (additive parameter)."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "Detector-X", "tier": "Device", "parent_id": str(uuid4())},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_register_asset_route_owners_field_validates_pairing() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={
                "name": "Detector-X",
                "tier": "Device",
                "parent_id": str(uuid4()),
                "owners": [
                    {
                        "name": "HZB",
                        "identifier": "02aj13c28",
                        # identifier_type missing -> pairing violation -> 400
                    }
                ],
            },
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_register_asset_route_409_when_payload_owner_names_collide() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={
                "name": "Detector-X",
                "tier": "Device",
                "parent_id": str(uuid4()),
                "owners": [
                    {"name": "HZB", "contact": "a@hzb.de"},
                    {"name": "HZB", "contact": "b@hzb.de"},
                ],
            },
        )
    assert response.status_code == 409
