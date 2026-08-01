"""Contract tests for `POST /datasets/{dataset_id}/promote`.

Promotes a Dataset from Trial intent to Production intent. Body
carries `reason` (1-500 chars). Strict guards: cannot promote
Discarded dataset; cannot promote when producing Run did not
Complete; cannot promote when any derived_from Dataset is still Trial.
Strict-not-idempotent: re-promoting returns 409.
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
def test_post_promote_dataset_returns_204_on_happy_path() -> None:
    """Standalone-upload Dataset (no producing_run_id, no derived_from):
    promotion succeeds with no integrity guards firing."""
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        response = client.post(
            f"/datasets/{dataset_id}/promote",
            json={"reason": "passed peer review for Smith et al 2026"},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_promote_dataset_returns_409_on_re_promote() -> None:
    """Strict-not-idempotent: second promote attempt returns 409."""
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        first = client.post(
            f"/datasets/{dataset_id}/promote",
            json={"reason": "passed review"},
        )
        assert first.status_code == 204
        second = client.post(
            f"/datasets/{dataset_id}/promote",
            json={"reason": "trying again"},
        )
    assert second.status_code == 409
    assert "promoted" in second.json()["detail"].lower()


@pytest.mark.contract
def test_post_promote_dataset_returns_409_on_discarded() -> None:
    """Discarded Datasets cannot be promoted (no point — bytes are gone)."""
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        client.post(
            f"/datasets/{dataset_id}/discard",
            json={"reason": "bytes purged"},
        )
        response = client.post(
            f"/datasets/{dataset_id}/promote",
            json={"reason": "trying"},
        )
    assert response.status_code == 409
    assert "discarded" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_promote_dataset_returns_404_for_unknown_dataset() -> None:
    with TestClient(create_app()) as client:
        unknown_id = uuid4()
        response = client.post(
            f"/datasets/{unknown_id}/promote",
            json={"reason": "trying"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_promote_dataset_returns_400_for_whitespace_reason() -> None:
    """The Pydantic min_length=1 catches empty; whitespace-only triggers
    domain validation via PromotionReason VO -> 400."""
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        response = client.post(
            f"/datasets/{dataset_id}/promote",
            json={"reason": "   "},
        )
    # FastAPI Pydantic's min_length=1 sees the string with whitespace as
    # length-3 and lets it through; the PromotionReason VO at the
    # decider then rejects after trim -> 400.
    assert response.status_code == 400


@pytest.mark.contract
def test_post_promote_dataset_returns_422_for_missing_reason() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register(client)
        response = client.post(
            f"/datasets/{dataset_id}/promote",
            json={},  # missing reason
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_promote_dataset_returns_422_for_malformed_path() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/datasets/not-a-uuid/promote",
            json={"reason": "anything"},
        )
    assert response.status_code == 422
