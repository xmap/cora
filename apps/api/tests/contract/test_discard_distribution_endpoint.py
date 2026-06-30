"""Contract tests for `POST /distributions/{distribution_id}/discard`.

Guarded confirm-before-purge: a copy may be marked Discarded only when
a sibling copy of the same Dataset is Verified on a different storage
tier and the parent Dataset is not Discarded. Strict-not-idempotent
(re-discarding raises 409). Body carries `reason` (1-500 chars).

## Scope

In a TestClient app there is no postgres pool and no projection
worker, so the default `dataset_distribution_lookup` is
`NoDatasetDistributionsLookup` and the cross-BC `SupplyLookup` stub
returns None for every id. Two consequences:

  - A Distribution cannot be registered through the wire (register
    needs SupplyLookup to resolve, which the stub never does), so the
    happy 204 path and the redundancy-success / last-Verified 409 paths
    are not reachable here. Those are locked at the unit + integration
    tiers (tests/unit/data/test_discard_distribution_decider.py,
    test_discard_distribution_handler.py).
  - The reachable wire-shape branches are the target-not-found 404 and
    the Pydantic body-schema 422s, plus the route's response_model +
    error_responses metadata pinned by the OpenAPI snapshot in
    test_committed_openapi_snapshot_matches_live_spec.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_discard_distribution_returns_404_when_distribution_missing() -> None:
    """Target stream is empty -> DistributionNotFoundError -> 404."""
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/distributions/{missing}/discard",
            json={"reason": "bytes reclaimed from cold tier"},
        )
    assert response.status_code == 404
    assert missing in response.json()["detail"]


@pytest.mark.contract
def test_post_discard_distribution_rejects_empty_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/distributions/{uuid4()}/discard",
            json={"reason": ""},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_discard_distribution_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/distributions/{uuid4()}/discard",
            json={"reason": "x" * 501},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_discard_distribution_rejects_invalid_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/distributions/not-a-uuid/discard",
            json={"reason": "X"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_discard_distribution_rejects_missing_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/distributions/{uuid4()}/discard",
            json={},
        )
    assert response.status_code == 422
