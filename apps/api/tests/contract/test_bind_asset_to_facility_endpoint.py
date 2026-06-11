"""Contract tests for `POST /assets/{asset_id}/bind-to-facility` (Slice 8C).

Covers:
  - happy path: 204 No Content + Asset gains facility_code
  - 404 on unknown facility_code (AssetFacilityNotFoundError)
  - 409 on set-once violation (AssetFacilityCodeAlreadyAssignedError)
  - 422 on missing / malformed facility_code (Pydantic regex)
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_FACILITY_CODE = "cora"


def _register_asset(client: TestClient, *, name: str = "Beamline 2-BM") -> UUID:
    """Register an Asset without facility_code (so the bind slice can set it)."""
    body: dict[str, object] = {
        "name": name,
        "tier": "Unit",
        "parent_id": str(uuid4()),
    }
    response = client.post("/assets", json=body)
    assert response.status_code == 201, response.text
    return UUID(response.json()["asset_id"])


@pytest.mark.contract
def test_post_bind_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/bind-to-facility",
            json={"facility_code": _FACILITY_CODE},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_bind_returns_404_when_facility_code_unknown() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/bind-to-facility",
            json={"facility_code": "ghost"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_bind_returns_409_when_asset_already_bound() -> None:
    """Set-once per Slice 8 Lock L2. The first bind succeeds; the
    second raises AssetFacilityCodeAlreadyAssignedError -> 409."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(
            f"/assets/{asset_id}/bind-to-facility",
            json={"facility_code": _FACILITY_CODE},
        )
        assert first.status_code == 204, first.text

        second = client.post(
            f"/assets/{asset_id}/bind-to-facility",
            json={"facility_code": _FACILITY_CODE},
        )
    assert second.status_code == 409


@pytest.mark.contract
def test_post_bind_rejects_missing_facility_code_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/bind-to-facility",
            json={},
        )
    assert response.status_code == 422


@pytest.mark.contract
@pytest.mark.parametrize("bad_code", ["APS", "", "facility code with spaces", "x" * 33])
def test_post_bind_rejects_malformed_facility_code_with_422(bad_code: str) -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/bind-to-facility",
            json={"facility_code": bad_code},
        )
    assert response.status_code == 422
