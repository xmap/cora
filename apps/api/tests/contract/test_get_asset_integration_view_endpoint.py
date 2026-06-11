"""Contract tests for `GET /assets/{asset_id}/integration-view`.

Read-time composition slice.
See [[project-asset-integration-view-design]] for the locked shape.

In TestClient mode the test-environment Kernel has no DB pool, so
applicable_capabilities falls back to empty list (the no-pool path).
Cautions also empty (AlwaysQuietCautionLookup). Asset / Family core
data flows through the InMemory event-store path.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(client: TestClient) -> str:
    body = {"name": "APS-2BM", "tier": "Unit", "parent_id": str(uuid4())}
    return client.post("/assets", json=body).json()["asset_id"]


@pytest.mark.contract
def test_get_integration_view_returns_200_on_known_asset() -> None:
    """Happy path: registered Asset returns 200 with the bundle shape."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.get(f"/assets/{asset_id}/integration-view")
    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == asset_id
    assert body["name"] == "APS-2BM"
    assert body["tier"] == "Unit"
    assert body["lifecycle"] == "Commissioned"
    assert body["condition"] == "Nominal"
    assert body["families"] == []
    assert body["ports"] == []
    assert body["settings"] == {}
    # In-memory test mode: no-pool fallback for capabilities; quiet
    # Caution-lookup for cautions.
    assert body["active_cautions"] == []
    assert body["applicable_capabilities"] == []
    assert body["incomplete"] is False


@pytest.mark.contract
def test_get_integration_view_returns_404_for_unknown_asset() -> None:
    with TestClient(create_app()) as client:
        unknown_id = uuid4()
        response = client.get(f"/assets/{unknown_id}/integration-view")
    assert response.status_code == 404


@pytest.mark.contract
def test_get_integration_view_returns_422_for_malformed_path() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/assets/not-a-uuid/integration-view")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_integration_view_carries_combined_family_affordances() -> None:
    """Asset with families exposes each Family's name + affordances
    in the bundle. Round-trip via REST."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        # Define a Family with a known affordance and add it to the Asset.
        family_id = client.post(
            "/families",
            json={"name": "RotaryStage", "affordances": ["Posable"]},
        ).json()["family_id"]
        client.post(
            f"/assets/{asset_id}/add-family",
            json={"family_id": family_id},
        )

        response = client.get(f"/assets/{asset_id}/integration-view")

    assert response.status_code == 200
    body = response.json()
    assert len(body["families"]) == 1
    family = body["families"][0]
    assert family["family_id"] == family_id
    assert family["name"] == "RotaryStage"
    assert family["affordances"] == ["Posable"]
    assert body["incomplete"] is False
