"""Contract tests for `POST /assets/{id}/remove-alternate-identifier`.

Mirror of `test_add_remove_asset_port_endpoints.py`'s remove section.
Verifies HTTP shape: 204 on happy path, 409 on
strict-not-idempotent / Decommissioned, 404 on missing asset,
422 on schema-validation failure, 400 on VO-validation failure.
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


def _add_alternate_identifier(
    client: TestClient, asset_id: str, *, kind: str = "SerialNumber", value: str = "XYZ-001"
) -> None:
    response = client.post(
        f"/assets/{asset_id}/add-alternate-identifier",
        json={"kind": kind, "value": value},
    )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_remove_alternate_identifier_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        _add_alternate_identifier(client, asset_id)
        response = client.post(
            f"/assets/{asset_id}/remove-alternate-identifier",
            json={"kind": "SerialNumber", "value": "XYZ-001"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_remove_alternate_identifier_returns_409_when_pair_not_found() -> None:
    """Strict-not-idempotent: removing without a prior add returns 409."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/remove-alternate-identifier",
            json={"kind": "SerialNumber", "value": "XYZ-001"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_remove_alternate_identifier_returns_409_when_kind_differs() -> None:
    """Exact (kind, value) pair: same value under wrong kind is a miss."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        _add_alternate_identifier(client, asset_id, kind="SerialNumber", value="ABC-9")
        response = client.post(
            f"/assets/{asset_id}/remove-alternate-identifier",
            json={"kind": "InventoryNumber", "value": "ABC-9"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_remove_alternate_identifier_returns_204_when_asset_decommissioned() -> None:
    """No lifecycle guard on alternate-identifier mutation: inventory
    tags may be reconciled even after retirement (audit correction,
    vendor RMA)."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        _add_alternate_identifier(client, asset_id)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(
            f"/assets/{asset_id}/remove-alternate-identifier",
            json={"kind": "SerialNumber", "value": "XYZ-001"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_remove_alternate_identifier_returns_404_for_missing_asset() -> None:
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing}/remove-alternate-identifier",
            json={"kind": "SerialNumber", "value": "XYZ-001"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_remove_alternate_identifier_returns_422_for_missing_required_field() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/remove-alternate-identifier",
            json={"kind": "SerialNumber"},  # missing value
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_remove_alternate_identifier_returns_422_for_invalid_kind() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/remove-alternate-identifier",
            json={"kind": "ROR", "value": "XYZ-001"},  # ROR belongs to Manufacturer
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_remove_alternate_identifier_returns_400_for_whitespace_only_value() -> None:
    """Pydantic min_length=1 catches "" but lets "   " through; the
    AlternateIdentifier VO then rejects with InvalidAlternateIdentifierError
    -> 400."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/remove-alternate-identifier",
            json={"kind": "SerialNumber", "value": "   "},
        )
    assert response.status_code == 400
