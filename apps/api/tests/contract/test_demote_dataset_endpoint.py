"""Contract tests for `POST /datasets/{dataset_id}/demote`.

Demotes a Dataset from Production intent to Retracted intent (terminal).
Body carries `reason` (1-500 chars). Strict guards: cannot demote
Discarded dataset; cannot demote Trial dataset (use discard for that).
Strict-not-idempotent: re-demoting returns 409.

First concrete instantiation of the Q4 compensation-primitive pattern;
see [[project-dataset-demote-design]].
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


def _register_and_promote(client: TestClient) -> str:
    """Register a Dataset and promote it to Production intent."""
    dataset_id = _register(client)
    client.post(
        f"/datasets/{dataset_id}/promote",
        json={"reason": "initial promotion"},
    )
    return dataset_id


@pytest.mark.contract
def test_post_demote_dataset_returns_204_on_happy_path() -> None:
    """Production Dataset demotes cleanly with a valid reason."""
    with TestClient(create_app()) as client:
        dataset_id = _register_and_promote(client)
        response = client.post(
            f"/datasets/{dataset_id}/demote",
            json={"reason": "discovered calibration error post-publication"},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_demote_dataset_returns_409_on_re_demote() -> None:
    """Strict-not-idempotent: second demote attempt returns 409."""
    with TestClient(create_app()) as client:
        dataset_id = _register_and_promote(client)
        first = client.post(
            f"/datasets/{dataset_id}/demote",
            json={"reason": "calibration error"},
        )
        assert first.status_code == 204
        second = client.post(
            f"/datasets/{dataset_id}/demote",
            json={"reason": "trying again"},
        )
    assert second.status_code == 409
    assert "retracted" in second.json()["detail"].lower()


@pytest.mark.contract
def test_post_demote_dataset_returns_409_on_discarded() -> None:
    """Discarded Datasets cannot be demoted (bytes are gone; Discarded
    is a stronger terminal than Retracted)."""
    with TestClient(create_app()) as client:
        dataset_id = _register_and_promote(client)
        client.post(
            f"/datasets/{dataset_id}/discard",
            json={"reason": "bytes purged"},
        )
        response = client.post(
            f"/datasets/{dataset_id}/demote",
            json={"reason": "trying"},
        )
    assert response.status_code == 409
    assert "discarded" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_demote_dataset_returns_409_on_trial_intent() -> None:
    """Trial Datasets cannot be demoted (semantically meaningless;
    use discard_dataset for Trial cleanup)."""
    with TestClient(create_app()) as client:
        dataset_id = _register(client)  # NOT promoted -> stays Trial
        response = client.post(
            f"/datasets/{dataset_id}/demote",
            json={"reason": "trying"},
        )
    assert response.status_code == 409
    assert "trial" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_demote_dataset_returns_404_for_unknown_dataset() -> None:
    with TestClient(create_app()) as client:
        unknown_id = uuid4()
        response = client.post(
            f"/datasets/{unknown_id}/demote",
            json={"reason": "trying"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_demote_dataset_returns_400_for_whitespace_reason() -> None:
    """Pydantic min_length=1 catches empty; whitespace-only triggers
    domain validation via DemotionReason VO -> 400."""
    with TestClient(create_app()) as client:
        dataset_id = _register_and_promote(client)
        response = client.post(
            f"/datasets/{dataset_id}/demote",
            json={"reason": "   "},
        )
    # Pydantic's min_length=1 sees the 3-char whitespace string and lets
    # it through; the DemotionReason VO at the decider then rejects after
    # trim -> 400.
    assert response.status_code == 400


@pytest.mark.contract
def test_post_demote_dataset_returns_422_for_missing_reason() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register_and_promote(client)
        response = client.post(
            f"/datasets/{dataset_id}/demote",
            json={},  # missing reason
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_demote_dataset_returns_422_for_malformed_path() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/datasets/not-a-uuid/demote",
            json={"reason": "anything"},
        )
    assert response.status_code == 422
