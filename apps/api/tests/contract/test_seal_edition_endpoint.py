"""Contract tests for `POST /editions/{edition_id}/seal`.

Seals a Registered Edition. Returns 200 on success, 404 when the
Edition or publisher Facility is missing or a member Dataset lacks
a canonical Distribution, 409 on FSM / membership conflicts.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _register_dataset(client: TestClient, *, name: str = "ds") -> str:
    response = client.post(
        "/datasets",
        json={
            "name": name,
            "uri": f"s3://b/{name}",
            "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
            "byte_size": 1024,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["dataset_id"]


def _promote_dataset(client: TestClient, dataset_id: str) -> None:
    response = client.post(
        f"/datasets/{dataset_id}/promote",
        json={"reason": "for publication"},
    )
    assert response.status_code in {200, 204}, response.text


def _register_edition(
    client: TestClient,
    *,
    dataset_ids: list[str],
    publisher_facility_code: str | None = "cora",
    license: str | None = "CC-BY-4.0",
    publication_year: int | None = 2026,
) -> str:
    body: dict[str, object] = {
        "kind": "ROCrate",
        "title": "Edition Title",
        "dataset_ids": dataset_ids,
        "creators": [
            {"actor_id": str(uuid4()), "affiliation": "ANL"},
        ],
    }
    if publisher_facility_code is not None:
        body["publisher_facility_code"] = publisher_facility_code
    if license is not None:
        body["license"] = license
    if publication_year is not None:
        body["publication_year"] = publication_year
    response = client.post("/editions", json=body)
    assert response.status_code == 201, response.text
    return response.json()["edition_id"]


# ---------- Wire shape ----------
#
# Happy path 200 requires a canonical Distribution for each member
# Dataset; the TestClient app uses the in-memory DistributionLookup
# adapter that the seal-handler resolves to None for every Dataset
# (no Postgres backing the projection here). The happy path is
# locked at the integration tier
# (tests/integration/test_seal_edition_handler_postgres.py).
# These contract tests cover wire-shape + error-mapping branches
# reachable in TestClient.


@pytest.mark.contract
def test_post_seal_edition_returns_404_when_distribution_missing() -> None:
    with TestClient(create_app()) as client:
        ds = _register_dataset(client, name="ds1")
        _promote_dataset(client, ds)
        edition_id = _register_edition(client, dataset_ids=[ds])
        response = client.post(f"/editions/{edition_id}/seal", json={})
    assert response.status_code == 404


# ---------- 404 ----------


@pytest.mark.contract
def test_post_seal_edition_returns_404_for_unknown_edition() -> None:
    with TestClient(create_app()) as client:
        unknown_id = uuid4()
        response = client.post(f"/editions/{unknown_id}/seal", json={})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_seal_edition_returns_404_for_unknown_publisher() -> None:
    with TestClient(create_app()) as client:
        ds = _register_dataset(client, name="ds1")
        _promote_dataset(client, ds)
        edition_id = _register_edition(client, dataset_ids=[ds])
        response = client.post(
            f"/editions/{edition_id}/seal",
            json={"publisher_facility_code": "no-such-facility"},
        )
    assert response.status_code == 404


# ---------- 409 ----------


@pytest.mark.contract
def test_post_seal_edition_returns_409_when_dataset_not_production() -> None:
    with TestClient(create_app()) as client:
        # Dataset NOT promoted -> remains Trial intent.
        ds = _register_dataset(client, name="ds1")
        edition_id = _register_edition(client, dataset_ids=[ds])
        response = client.post(f"/editions/{edition_id}/seal", json={})
    assert response.status_code == 409


# Note: 409 already-sealed + 409 license-required-for-kind cases depend
# on a happy-path seal completing first, which requires a canonical
# Distribution row (not available in TestClient without Postgres). Both
# branches are exercised at the unit-decider + integration-postgres tiers.
