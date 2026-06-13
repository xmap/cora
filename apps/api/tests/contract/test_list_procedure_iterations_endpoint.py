"""Contract tests for `GET /procedures/{procedure_id}/iterations`.

Read slice; 200 + items list. In the in-memory test app there is no
Postgres pool, so the handler short-circuits to an empty list (real
per-iteration rows are asserted in the Postgres integration suite). This
pins the response shape + path-param validation.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_get_iterations_returns_200_and_items_list() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/procedures/{uuid4()}/iterations")
    assert response.status_code == 200
    body = response.json()
    assert body == {"items": []}


@pytest.mark.contract
def test_get_iterations_returns_422_for_malformed_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/procedures/not-a-uuid/iterations")
    assert response.status_code == 422
