"""Contract tests for `POST /calibrations/{calibration_id}/revisions/{revision_id}/publish`.

The publish_revision slice's HTTP wire surface: 201 + receipt_id on
success, 403 / 404 / 409 mapping for the publish-time domain
rejections. Exercises the create_app() FastAPI surface end-to-end
against the in-memory adapters wired by make_inmemory_kernel.

The peer Permit must be registered against the test app's permit
lookup BEFORE the publish call; the test inspects
`app.state.calibration` to reach the lookup and seed the outbound
Permit.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.adapters.in_memory_permit_lookup import InMemoryPermitLookup


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


def _seed_calibration_and_revision(client: TestClient) -> tuple[str, str]:
    define_response = client.post("/calibrations", json=_define_body())
    assert define_response.status_code == 201, define_response.text
    cid = str(define_response.json()["calibration_id"])
    revision_response = client.post(f"/calibrations/{cid}/revisions", json=_revision_body())
    assert revision_response.status_code == 201, revision_response.text
    revision_id = str(revision_response.json()["revision_id"])
    return cid, revision_id


def _seed_outbound_permit(app: FastAPI, peer_facility_id: str = "aps-2bm") -> UUID:
    permit_lookup = app.state.deps.permit_lookup
    assert isinstance(permit_lookup, InMemoryPermitLookup)
    permit_id = uuid4()
    permit_lookup.register_outbound(
        peer_facility_id=peer_facility_id,
        artifact_kind="CalibrationRevision",
        permit_id=permit_id,
    )
    return permit_id


@pytest.mark.contract
def test_post_publish_returns_201_with_receipt_id_on_happy_path() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid, revision_id = _seed_calibration_and_revision(client)
        _seed_outbound_permit(app)
        response = client.post(
            f"/calibrations/{cid}/revisions/{revision_id}/publish",
            json={"peer_facility_id": "aps-2bm"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "receipt_id" in body
    UUID(body["receipt_id"])


@pytest.mark.contract
def test_post_publish_returns_404_when_calibration_missing() -> None:
    app = create_app()
    with TestClient(app) as client:
        _seed_outbound_permit(app)
        unknown_calibration = uuid4()
        unknown_revision = uuid4()
        response = client.post(
            f"/calibrations/{unknown_calibration}/revisions/{unknown_revision}/publish",
            json={"peer_facility_id": "aps-2bm"},
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_publish_returns_404_when_revision_missing_on_existing_calibration() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid, _ = _seed_calibration_and_revision(client)
        _seed_outbound_permit(app)
        unknown_revision = uuid4()
        response = client.post(
            f"/calibrations/{cid}/revisions/{unknown_revision}/publish",
            json={"peer_facility_id": "aps-2bm"},
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
def test_post_publish_returns_409_when_no_active_outbound_permit_for_peer() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid, revision_id = _seed_calibration_and_revision(client)
        response = client.post(
            f"/calibrations/{cid}/revisions/{revision_id}/publish",
            json={"peer_facility_id": "unknown-peer"},
        )
    assert response.status_code == 409, response.text


@pytest.mark.contract
def test_post_publish_rejects_missing_peer_facility_id_with_422() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid, revision_id = _seed_calibration_and_revision(client)
        response = client.post(
            f"/calibrations/{cid}/revisions/{revision_id}/publish",
            json={},
        )
    assert response.status_code == 422, response.text


@pytest.mark.contract
def test_post_publish_returns_422_for_malformed_uuid_path_param() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/calibrations/not-a-uuid/revisions/also-not-a-uuid/publish",
            json={"peer_facility_id": "aps-2bm"},
        )
    assert response.status_code == 422, response.text


@pytest.mark.contract
def test_post_publish_accepts_idempotency_key_header() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid, revision_id = _seed_calibration_and_revision(client)
        _seed_outbound_permit(app)
        response = client.post(
            f"/calibrations/{cid}/revisions/{revision_id}/publish",
            json={"peer_facility_id": "aps-2bm"},
            headers={"Idempotency-Key": "publish-key"},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_publish_response_body_carries_receipt_id_field() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid, revision_id = _seed_calibration_and_revision(client)
        _seed_outbound_permit(app)
        response = client.post(
            f"/calibrations/{cid}/revisions/{revision_id}/publish",
            json={"peer_facility_id": "aps-2bm"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body.keys()) == {"receipt_id"}
