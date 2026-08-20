"""Contract tests for `POST /distributions/{distribution_id}/mark-stale`.

Records a fact about the world (the bytes at this location are gone or
no longer trusted); unlike discard_distribution's guarded
confirm-before-purge, there is no redundancy guard and no parent-Dataset
guard. The only refusal is a target already Discarded (terminal). Body
carries `reason` (1-500 chars).

## Scope

In a TestClient app there is no postgres pool and no projection
worker, so a Distribution cannot be registered through the wire (the
cross-BC SupplyLookup stub returns None for every id). The happy 204
path and the already-Discarded 409 path are therefore not reachable
here; those are locked at the unit tier
(tests/unit/data/test_mark_distribution_stale_decider.py,
test_mark_distribution_stale_handler.py). The reachable wire-shape
branches are the target-not-found 404 and the Pydantic body-schema
422s, plus the route's response_model + error_responses metadata
pinned by the OpenAPI snapshot in
test_committed_openapi_snapshot_matches_live_spec.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_mark_distribution_stale_returns_404_when_distribution_missing() -> None:
    """Target stream is empty -> DistributionNotFoundError -> 404."""
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/distributions/{missing}/mark-stale",
            json={"reason": "storage array declared dead by operations"},
        )
    assert response.status_code == 404
    assert missing in response.json()["detail"]


@pytest.mark.contract
def test_post_mark_distribution_stale_rejects_empty_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/distributions/{uuid4()}/mark-stale",
            json={"reason": ""},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_distribution_stale_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/distributions/{uuid4()}/mark-stale",
            json={"reason": "x" * 501},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_distribution_stale_rejects_invalid_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/distributions/not-a-uuid/mark-stale",
            json={"reason": "X"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_mark_distribution_stale_rejects_missing_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/distributions/{uuid4()}/mark-stale",
            json={},
        )
    assert response.status_code == 422
