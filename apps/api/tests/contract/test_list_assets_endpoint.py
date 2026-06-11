"""Contract tests for `GET /assets`."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_assets_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/assets")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize(
    "tier",
    ["Unit", "Component", "Device"],
)
def test_get_assets_accepts_each_tier(client: TestClient, tier: str) -> None:
    with client:
        response = client.get(f"/assets?tier={tier}")
    assert response.status_code == 200


@pytest.mark.contract
@pytest.mark.parametrize(
    "lifecycle",
    ["Commissioned", "Active", "Maintenance", "Decommissioned"],
)
def test_get_assets_accepts_each_lifecycle(client: TestClient, lifecycle: str) -> None:
    with client:
        response = client.get(f"/assets?lifecycle={lifecycle}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_assets_rejects_unknown_tier_with_422(client: TestClient) -> None:
    """Lowercase 'unit' is NOT in the Literal (PascalCase only)."""
    with client:
        response = client.get("/assets?tier=unit")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_assets_rejects_unknown_lifecycle_with_422(
    client: TestClient,
) -> None:
    with client:
        response = client.get("/assets?lifecycle=zombie")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_assets_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/assets?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_assets_rejects_invalid_parent_id_with_422(
    client: TestClient,
) -> None:
    """parent_id must be a valid UUID."""
    with client:
        response = client.get("/assets?parent_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_assets_rejects_limit_zero_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/assets?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_assets_rejects_limit_above_cap_with_422(
    client: TestClient,
) -> None:
    with client:
        response = client.get("/assets?limit=101")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_assets_combines_filters(client: TestClient) -> None:
    """All three filters can be set together."""
    import uuid

    with client:
        response = client.get(f"/assets?tier=Device&lifecycle=Active&parent_id={uuid.uuid4()}")
    assert response.status_code == 200
