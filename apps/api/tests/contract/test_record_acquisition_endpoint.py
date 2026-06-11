"""Contract tests for `POST /acquisitions`.

Happy-path 201, 403 (authz deny), 404 (cross-aggregate not-found),
409 (Capturing-affordance miss / already-exists), and 422 (schema)
mappings. Success + business-error cases override the handler
dependency (the in-memory AssetLookup is empty in the test app, so a
real-stack happy path cannot resolve a Capturing-bearing Asset); the
404 dataset case exercises the real stack.
"""

# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.acquisition import (
    AcquisitionAlreadyExistsError,
    AcquisitionAssetNotFoundError,
    AcquisitionCannotRecordWithoutCapturingError,
)
from cora.data.errors import UnauthorizedError
from cora.data.features.record_acquisition.route import _get_handler

_CAPTURED_AT = datetime(2026, 6, 10, 9, 0, 0, tzinfo=UTC).isoformat()


def _body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "dataset_id": str(uuid4()),
        "producing_asset_id": str(uuid4()),
        "captured_at": _CAPTURED_AT,
        "settings": {"exposure_ms": 200},
        "evidence": {},
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_acquisitions_returns_201_with_acquisition_id() -> None:
    app = create_app()
    new_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        return new_id

    app.dependency_overrides[_get_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/acquisitions", json=_body())
    assert response.status_code == 201
    assert response.json()["acquisition_id"] == str(new_id)


@pytest.mark.contract
def test_post_acquisitions_accepts_null_producing_run_id() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        return uuid4()

    app.dependency_overrides[_get_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/acquisitions", json=_body(producing_run_id=None))
    assert response.status_code == 201


@pytest.mark.contract
def test_post_acquisitions_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/acquisitions", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_acquisitions_returns_404_when_dataset_unseeded() -> None:
    """Real-stack: an unknown dataset_id resolves to None and the
    handler raises DatasetNotFoundError -> 404."""
    with TestClient(create_app()) as client:
        response = client.post("/acquisitions", json=_body())
    assert response.status_code == 404


@pytest.mark.contract
def test_post_acquisitions_returns_404_when_asset_unseeded() -> None:
    app = create_app()
    asset_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise AcquisitionAssetNotFoundError(asset_id)

    app.dependency_overrides[_get_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/acquisitions", json=_body())
    assert response.status_code == 404


@pytest.mark.contract
def test_post_acquisitions_returns_409_on_missing_capturing_affordance() -> None:
    app = create_app()
    asset_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise AcquisitionCannotRecordWithoutCapturingError(asset_id)

    app.dependency_overrides[_get_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/acquisitions", json=_body())
    assert response.status_code == 409
    assert "Capturing" in response.json()["detail"]


@pytest.mark.contract
def test_post_acquisitions_returns_409_on_already_exists() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise AcquisitionAlreadyExistsError(uuid4())

    app.dependency_overrides[_get_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/acquisitions", json=_body())
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_acquisitions_returns_422_on_missing_required_field() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/acquisitions",
            json={"producing_asset_id": str(uuid4()), "captured_at": _CAPTURED_AT},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_acquisitions_returns_422_on_extra_field() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/acquisitions", json=_body(unexpected="x"))
    assert response.status_code == 422
