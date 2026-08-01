"""Contract tests for `POST /subjects/{subject_id}/dismount`.

Action endpoint with body `{reason}`. 204 on success; 409 on
disallowed source state; 404 on missing subject; 422 on bad body.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._subject_helpers import register_active_asset


def _register_subject(client: TestClient, *, name: str = "Sample-A1") -> str:
    response = client.post("/subjects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["subject_id"]


def _mount(client: TestClient, subject_id: str, asset_id: str) -> None:
    response = client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": asset_id, "reason": "test mount"},
    )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_dismount_returns_204_from_mounted() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        asset_id = register_active_asset(client)
        _mount(client, subject_id, asset_id)
        response = client.post(
            f"/subjects/{subject_id}/dismount",
            json={"reason": "run complete"},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_dismount_returns_204_from_measured() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        asset_id = register_active_asset(client)
        _mount(client, subject_id, asset_id)
        measure = client.post(f"/subjects/{subject_id}/measure")
        assert measure.status_code == 204
        response = client.post(
            f"/subjects/{subject_id}/dismount",
            json={"reason": "moving to next stage"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_dismount_returns_409_when_subject_only_received() -> None:
    """Strict-not-idempotent: dismounting a never-mounted Subject raises."""
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        response = client.post(
            f"/subjects/{subject_id}/dismount",
            json={"reason": "x"},
        )
    assert response.status_code == 409
    body = response.json()
    assert "Mounted" in body["detail"]
    assert "Measured" in body["detail"]


@pytest.mark.contract
def test_post_dismount_returns_404_when_subject_missing() -> None:
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/subjects/{missing}/dismount",
            json={"reason": "x"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_dismount_returns_422_when_reason_missing() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        response = client.post(f"/subjects/{subject_id}/dismount", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_dismount_returns_422_when_reason_empty() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        response = client.post(
            f"/subjects/{subject_id}/dismount",
            json={"reason": ""},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_dismount_then_remount_cycle() -> None:
    """Pin the multi-stage workflow that 4f enables: mount on A,
    dismount, mount on B (different Asset). Both mounts succeed."""
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        asset_a = register_active_asset(client, name="Stage-A")
        asset_b = register_active_asset(client, name="Stage-B")

        first_mount = client.post(
            f"/subjects/{subject_id}/mount",
            json={"asset_id": asset_a, "reason": "alignment"},
        )
        assert first_mount.status_code == 204

        dismount = client.post(
            f"/subjects/{subject_id}/dismount",
            json={"reason": "moving to detector"},
        )
        assert dismount.status_code == 204

        second_mount = client.post(
            f"/subjects/{subject_id}/mount",
            json={"asset_id": asset_b, "reason": "loaded for scan"},
        )
        assert second_mount.status_code == 204

        # get_subject reflects the second Asset.
        body = client.get(f"/subjects/{subject_id}").json()
        assert body["status"] == "Mounted"
        assert body["mounted_on_asset_id"] == asset_b


@pytest.mark.contract
def test_dismounted_subject_can_be_removed_directly() -> None:
    """4f: post-dismount Subject is in Received status, so
    remove_subject's widened source set allows direct removal
    without going through Mounted again."""
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        asset_id = register_active_asset(client)
        _mount(client, subject_id, asset_id)
        client.post(f"/subjects/{subject_id}/dismount", json={"reason": "done"})
        # Subject is now Received; remove should succeed directly.
        response = client.post(f"/subjects/{subject_id}/remove")
    assert response.status_code == 204
