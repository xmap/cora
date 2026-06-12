"""Contract tests for `POST /assets/mint-missing-persistent-ids`.

`APP_ENV=test` wires `InMemoryEventStore` with `pool=None`, so enumeration
finds nothing: these pin the WIRE contract (route wired, 200 + response shape,
request-body validation). The end-to-end sweep against a real projection lives
in `tests/integration/equipment/test_mint_missing_asset_persistent_ids_postgres.py`.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_mint_missing_returns_200_with_empty_sweep_in_memory() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/assets/mint-missing-persistent-ids", json={})
    assert response.status_code == 200, response.text
    assert response.json() == {"scanned": 0, "minted": [], "skipped": [], "failed": []}


@pytest.mark.contract
def test_post_mint_missing_accepts_explicit_body() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets/mint-missing-persistent-ids",
            json={"scheme": "Handle", "facility_code": "aps", "limit": 10},
        )
    assert response.status_code == 200, response.text
    assert response.json()["scanned"] == 0


@pytest.mark.contract
@pytest.mark.parametrize(
    "body",
    [
        {"limit": 0},  # below ge=1
        {"limit": 1001},  # above le=1000
        {"scheme": "ARK"},  # outside the closed scheme enum
        {"unknown": "x"},  # extra fields forbidden
    ],
)
def test_post_mint_missing_rejects_invalid_body_422(body: dict[str, object]) -> None:
    with TestClient(create_app()) as client:
        response = client.post("/assets/mint-missing-persistent-ids", json=body)
    assert response.status_code == 422, response.text
