"""Contract tests for `POST /calibrations/{calibration_id}/revisions`."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.calibration.aggregates.calibration import CalibrationNotFoundError
from cora.calibration.errors import UnauthorizedError
from cora.calibration.features.append_calibration_revision.route import (
    _get_handler as _get_append_calibration_revision_handler,  # pyright: ignore[reportPrivateUsage]
)


def _define_body(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "target_id": str(uuid4()),
        "quantity": "rotation_center",
        "operating_point": {"energy": 25.0, "optics_config": "5x"},
    }
    base.update(overrides)
    return base


def _revision_body(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "value": {"center": 1024.5, "uncertainty": 0.3},
        "status": "Provisional",
        "source": {"kind": "Measured", "procedure_id": str(uuid4())},
    }
    base.update(overrides)
    return base


def _seed_calibration(client: TestClient) -> str:
    response = client.post("/calibrations", json=_define_body())
    assert response.status_code == 201, response.text
    return str(response.json()["calibration_id"])


@pytest.mark.contract
def test_post_revisions_returns_201_with_revision_id() -> None:
    with TestClient(create_app()) as client:
        cid = _seed_calibration(client)
        response = client.post(f"/calibrations/{cid}/revisions", json=_revision_body())
    assert response.status_code == 201, response.text
    body = response.json()
    assert "revision_id" in body
    UUID(body["revision_id"])


@pytest.mark.contract
def test_post_revisions_accepts_each_source_kind() -> None:
    with TestClient(create_app()) as client:
        cid = _seed_calibration(client)
        for source in [
            {"kind": "Measured", "procedure_id": str(uuid4())},
            {"kind": "Computed", "dataset_id": str(uuid4())},
            {"kind": "Asserted", "asserted_by": str(uuid4())},
        ]:
            response = client.post(
                f"/calibrations/{cid}/revisions",
                json=_revision_body(source=source),
            )
            assert response.status_code == 201, response.text


@pytest.mark.contract
@pytest.mark.parametrize("status_value", ["Provisional", "Verified"])
def test_post_revisions_accepts_each_status(status_value: str) -> None:
    with TestClient(create_app()) as client:
        cid = _seed_calibration(client)
        response = client.post(
            f"/calibrations/{cid}/revisions",
            json=_revision_body(status=status_value),
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_revisions_rejects_unknown_status_with_422() -> None:
    """3rd tier `Refined` deferred to phase 12f."""
    with TestClient(create_app()) as client:
        cid = _seed_calibration(client)
        response = client.post(
            f"/calibrations/{cid}/revisions",
            json=_revision_body(status="Refined"),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revisions_rejects_unknown_source_kind_with_422() -> None:
    with TestClient(create_app()) as client:
        cid = _seed_calibration(client)
        response = client.post(
            f"/calibrations/{cid}/revisions",
            json=_revision_body(source={"kind": "Inferred", "procedure_id": str(uuid4())}),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revisions_rejects_missing_required_value_key_with_400() -> None:
    """rotation_center value_schema requires center."""
    with TestClient(create_app()) as client:
        cid = _seed_calibration(client)
        response = client.post(
            f"/calibrations/{cid}/revisions",
            json=_revision_body(value={"uncertainty": 0.3}),
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_revisions_rejects_empty_value_with_400() -> None:
    with TestClient(create_app()) as client:
        cid = _seed_calibration(client)
        response = client.post(
            f"/calibrations/{cid}/revisions",
            json=_revision_body(value={}),
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_revisions_rejects_supersedes_revision_not_on_aggregate_with_400() -> None:
    """Cross-aggregate supersession is forbidden."""
    with TestClient(create_app()) as client:
        cid = _seed_calibration(client)
        response = client.post(
            f"/calibrations/{cid}/revisions",
            json=_revision_body(supersedes_revision_id=str(uuid4())),
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_revisions_returns_404_when_calibration_missing() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/calibrations/{uuid4()}/revisions",
            json=_revision_body(),
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_revisions_returns_422_for_malformed_uuid_path_param() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/calibrations/not-a-uuid/revisions",
            json=_revision_body(),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_revisions_returns_404_when_handler_raises_not_found() -> None:
    """Defensive: the handler may surface CalibrationNotFoundError for
    valid-shape ids that don't resolve. Mapped to 404 by the routes."""
    app = create_app()
    missing_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise CalibrationNotFoundError(missing_id)

    app.dependency_overrides[_get_append_calibration_revision_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/calibrations/{missing_id}/revisions",
            json=_revision_body(),
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_revisions_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_append_calibration_revision_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/calibrations/{uuid4()}/revisions",
            json=_revision_body(),
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
