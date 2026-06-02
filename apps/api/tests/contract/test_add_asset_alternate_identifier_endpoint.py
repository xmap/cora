"""Contract tests for `POST /assets/{id}/add-alternate-identifier`.

Mirror of `test_remove_asset_alternate_identifier_endpoint.py`.
Verifies HTTP shape: 204 on happy path, 409 on
strict-not-idempotent duplicate, 404 on missing asset, 422 on
schema-validation failure, 400 on VO-validation failure. There is
NO lifecycle guard, so the Decommissioned-asset case returns 204.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(client: TestClient) -> str:
    response = client.post(
        "/assets",
        json={"name": "Detector-X", "level": "Device", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["asset_id"]
    return asset_id


@pytest.mark.contract
def test_post_add_alternate_identifier_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-alternate-identifier",
            json={"kind": "SerialNumber", "value": "XYZ-001"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_add_alternate_identifier_returns_409_when_pair_already_present() -> None:
    """Strict-not-idempotent: a duplicate (kind, value) pair returns 409."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(
            f"/assets/{asset_id}/add-alternate-identifier",
            json={"kind": "SerialNumber", "value": "XYZ-001"},
        )
        assert first.status_code == 204
        second = client.post(
            f"/assets/{asset_id}/add-alternate-identifier",
            json={"kind": "SerialNumber", "value": "XYZ-001"},
        )
    assert second.status_code == 409
    assert "XYZ-001" in second.json()["detail"]


@pytest.mark.contract
def test_post_add_alternate_identifier_allows_same_value_under_different_kind() -> None:
    """Uniqueness keyed on the (kind, value) pair; same value under a
    different kind is a distinct identifier."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(
            f"/assets/{asset_id}/add-alternate-identifier",
            json={"kind": "SerialNumber", "value": "ABC-9"},
        )
        assert first.status_code == 204
        second = client.post(
            f"/assets/{asset_id}/add-alternate-identifier",
            json={"kind": "InventoryNumber", "value": "ABC-9"},
        )
    assert second.status_code == 204


@pytest.mark.contract
def test_post_add_alternate_identifier_returns_204_when_asset_decommissioned() -> None:
    """No lifecycle guard: inventory tags may be added even after
    retirement (audit correction, vendor RMA)."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(
            f"/assets/{asset_id}/add-alternate-identifier",
            json={"kind": "SerialNumber", "value": "XYZ-001"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_add_alternate_identifier_returns_404_for_missing_asset() -> None:
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing}/add-alternate-identifier",
            json={"kind": "SerialNumber", "value": "XYZ-001"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_alternate_identifier_returns_422_for_missing_required_field() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-alternate-identifier",
            json={"kind": "SerialNumber"},  # missing value
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_alternate_identifier_returns_422_for_invalid_kind() -> None:
    """`ROR` is a Manufacturer-level scheme on Model; it is NOT in the
    AlternateIdentifierKind enum on the Asset instance side."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-alternate-identifier",
            json={"kind": "ROR", "value": "XYZ-001"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_alternate_identifier_returns_400_for_whitespace_only_value() -> None:
    """Pydantic `min_length=1` catches "" but lets "   " through; the
    AlternateIdentifier VO then rejects with
    InvalidAlternateIdentifierValueError -> 400."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-alternate-identifier",
            json={"kind": "SerialNumber", "value": "   "},
        )
    assert response.status_code == 400
