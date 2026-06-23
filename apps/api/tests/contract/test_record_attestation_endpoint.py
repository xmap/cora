"""Contract tests for ``POST /attestations``.

Genesis create-style endpoint. The body is slim: ``dataset_id`` (always),
``distribution_id`` (optional), and ``kind``. CORA computes the checksum
itself, so the request carries no outcome or evidence.

## Scope

In a TestClient app the Distribution stream is not pre-seeded (the
in-memory SupplyLookup stub cannot resolve a Supply, so a Distribution
cannot be registered without Postgres). We exercise the boundary reachable
in-memory:

  - 404: dataset_id never seeded; distribution_id never seeded.
  - 400: kind not yet supported (handler-tier rejection).
  - 422: Pydantic schema failures (unknown kind, extra top-level key,
         invalid UUID).

The verifier-driven paths (Match/Mismatch/Unreachable, unsupported-scheme
400) require a real Distribution and are covered by the integration suite.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_GOOD_SHA = "a" * 64


def _register_dataset(client: TestClient) -> str:
    response = client.post(
        "/datasets",
        json={
            "name": "parent-dataset",
            "uri": "s3://aps-32id/runs/abc/recon.h5",
            "checksum": {"algorithm": "sha256", "value": _GOOD_SHA},
            "byte_size": 1024,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["dataset_id"]


def _good_body(
    *,
    dataset_id: str | None = None,
    distribution_id: str | None = None,
    **overrides: object,
) -> dict[str, object]:
    base: dict[str, object] = {
        "dataset_id": dataset_id or str(uuid4()),
        "distribution_id": distribution_id or str(uuid4()),
        "kind": "ChecksumVerified",
    }
    base.update(overrides)
    return base


# ---------- Cross-aggregate not-found (404) ----------


@pytest.mark.contract
def test_post_attestations_returns_404_when_dataset_id_does_not_exist() -> None:
    missing_dataset = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/attestations",
            json=_good_body(dataset_id=missing_dataset),
        )
    assert response.status_code == 404
    assert missing_dataset in response.json()["detail"]


@pytest.mark.contract
def test_post_attestations_returns_404_when_distribution_id_does_not_exist() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register_dataset(client)
        distribution_id = str(uuid4())
        response = client.post(
            "/attestations",
            json=_good_body(dataset_id=dataset_id, distribution_id=distribution_id),
        )
    assert response.status_code == 404
    assert distribution_id in response.json()["detail"]


# ---------- Handler-tier 400 ----------


@pytest.mark.contract
def test_post_attestations_returns_400_for_kind_not_yet_supported() -> None:
    """FormatValidated / BitRotChecked / ConformsToValidated are valid
    enum values (422 does not fire) but lift to 400 because no concrete
    arm exists today."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/attestations",
            json=_good_body(kind="BitRotChecked"),
        )
    assert response.status_code == 400
    assert "BitRotChecked" in response.json()["detail"]


# ---------- Schema validation (422) ----------


@pytest.mark.contract
def test_post_attestations_rejects_unknown_kind_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/attestations",
            json=_good_body(kind="HashChecked"),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_attestations_rejects_extra_top_level_field_with_422() -> None:
    with TestClient(create_app()) as client:
        body = _good_body()
        body["extra_field"] = "boom"
        response = client.post("/attestations", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_attestations_rejects_invalid_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/attestations",
            json=_good_body(dataset_id="not-a-uuid"),
        )
    assert response.status_code == 422
