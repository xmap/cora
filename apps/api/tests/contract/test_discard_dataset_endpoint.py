"""Contract tests for `POST /datasets/{dataset_id}/discard`.

Single-source terminal: `Registered -> Discarded`. Strict-not-
idempotent (re-discarding raises 409). Body carries `reason`
(1-500 chars).
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _register(client: TestClient, **overrides: object) -> str:
    body: dict[str, object] = {
        "name": "D",
        "uri": "s3://b/k",
        "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
        "byte_size": 0,
        "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
    }
    body.update(overrides)
    return client.post("/datasets", json=body).json()["dataset_id"]


@pytest.mark.contract
def test_post_discard_dataset_returns_204_from_registered() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        response = client.post(
            f"/datasets/{dataset_id}/discard",
            json={"reason": "GDPR Article 17 erasure request"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_discard_dataset_round_trips_into_get_dataset_status_discarded() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        client.post(f"/datasets/{dataset_id}/discard", json={"reason": "X"})
        response = client.get(f"/datasets/{dataset_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "Discarded"


@pytest.mark.contract
def test_post_discard_dataset_returns_404_when_dataset_does_not_exist() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/datasets/{uuid4()}/discard",
            json={"reason": "X"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_discard_dataset_returns_409_when_already_discarded() -> None:
    """Strict-not-idempotent: re-discarding raises 409."""
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        first = client.post(f"/datasets/{dataset_id}/discard", json={"reason": "first"})
        assert first.status_code == 204
        second = client.post(f"/datasets/{dataset_id}/discard", json={"reason": "second"})
    assert second.status_code == 409
    assert "Discarded" in second.json()["detail"]


@pytest.mark.contract
def test_post_discard_dataset_rejects_empty_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        response = client.post(f"/datasets/{dataset_id}/discard", json={"reason": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_discard_dataset_rejects_whitespace_only_reason_with_400() -> None:
    """Whitespace passes Pydantic; decider trims and rejects."""
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        response = client.post(f"/datasets/{dataset_id}/discard", json={"reason": "   "})
    assert response.status_code == 400
    assert "discard reason" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_discard_dataset_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        response = client.post(
            f"/datasets/{dataset_id}/discard",
            json={"reason": "x" * 501},
        )
    assert response.status_code == 422


# ---------- 7b lineage tightening ----------


@pytest.mark.contract
def test_post_datasets_returns_409_when_derived_from_id_is_discarded() -> None:
    """7b tightening: cannot derive a new Dataset from a Discarded source."""
    with TestClient(create_app()) as client:
        upstream_id = _register(client, name="upstream")
        client.post(
            f"/datasets/{upstream_id}/discard",
            json={"reason": "purged"},
        )
        response = client.post(
            "/datasets",
            json={
                "name": "derived",
                "uri": "s3://b/derived",
                "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
                "byte_size": 0,
                "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
                "derived_from": [upstream_id],
            },
        )
    assert response.status_code == 409
    assert "Discarded" in response.json()["detail"]
    assert upstream_id in response.json()["detail"]


@pytest.mark.contract
def test_post_datasets_409_message_lists_all_discarded_derived_from_ids() -> None:
    with TestClient(create_app()) as client:
        a = _register(client, name="a")
        b = _register(client, name="b")
        client.post(f"/datasets/{a}/discard", json={"reason": "purge a"})
        client.post(f"/datasets/{b}/discard", json={"reason": "purge b"})
        response = client.post(
            "/datasets",
            json={
                "name": "derived",
                "uri": "s3://b/derived",
                "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
                "byte_size": 0,
                "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
                "derived_from": [a, b],
            },
        )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert a in detail
    assert b in detail
