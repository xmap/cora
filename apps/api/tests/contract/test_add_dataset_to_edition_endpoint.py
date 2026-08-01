"""Contract tests for `POST /editions/{edition_id}/datasets/{dataset_id}`.

Adds an existing Dataset to a Registered Edition. Returns 204 on
success, 404 when Edition or Dataset is missing, 409 when the
Edition is not in Registered state or the Dataset is already a
member / is Discarded.
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


def _register_edition(client: TestClient, *, dataset_ids: list[str]) -> str:
    response = client.post(
        "/editions",
        json={
            "kind": "ROCrate",
            "title": "Edition Title",
            "dataset_ids": dataset_ids,
            "creators": [
                {"actor_id": str(uuid4()), "affiliation": "ANL"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["edition_id"]


# ---------- Happy ----------


@pytest.mark.contract
def test_post_edition_datasets_returns_204_on_success() -> None:
    with TestClient(create_app()) as client:
        first = _register_dataset(client, name="first")
        edition_id = _register_edition(client, dataset_ids=[first])
        second = _register_dataset(client, name="second")
        response = client.post(f"/editions/{edition_id}/datasets/{second}")
    assert response.status_code == 204
    assert response.content == b""


# ---------- 404 ----------


@pytest.mark.contract
def test_post_edition_datasets_returns_404_for_unknown_edition() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register_dataset(client)
        unknown_edition = uuid4()
        response = client.post(f"/editions/{unknown_edition}/datasets/{dataset_id}")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_edition_datasets_returns_404_for_unknown_dataset() -> None:
    with TestClient(create_app()) as client:
        first = _register_dataset(client, name="first")
        edition_id = _register_edition(client, dataset_ids=[first])
        unknown_dataset = uuid4()
        response = client.post(f"/editions/{edition_id}/datasets/{unknown_dataset}")
    assert response.status_code == 404


# ---------- 409 ----------


@pytest.mark.contract
def test_post_edition_datasets_returns_409_when_dataset_already_member() -> None:
    with TestClient(create_app()) as client:
        first = _register_dataset(client, name="first")
        edition_id = _register_edition(client, dataset_ids=[first])
        response = client.post(f"/editions/{edition_id}/datasets/{first}")
    assert response.status_code == 409


@pytest.mark.contract
def test_post_edition_datasets_returns_409_when_dataset_discarded() -> None:
    with TestClient(create_app()) as client:
        first = _register_dataset(client, name="first")
        edition_id = _register_edition(client, dataset_ids=[first])
        second = _register_dataset(client, name="second")
        discard = client.post(
            f"/datasets/{second}/discard",
            json={"reason": "bytes purged"},
        )
        assert discard.status_code == 204, discard.text
        response = client.post(f"/editions/{edition_id}/datasets/{second}")
    assert response.status_code == 409


# ---------- 422 ----------


@pytest.mark.contract
def test_post_edition_datasets_rejects_malformed_path_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/editions/not-a-uuid/datasets/{uuid4()}")
    assert response.status_code == 422
