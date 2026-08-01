"""Contract tests for `GET /cautions/{caution_id}`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.caution.errors import UnauthorizedError
from cora.caution.features.get_caution.route import (
    _get_handler as _get_get_caution_handler,  # pyright: ignore[reportPrivateUsage]
)


def _seed(client: TestClient, **overrides: object) -> tuple[str, dict[str, object]]:
    asset_id = str(uuid4())
    body: dict[str, object] = {
        "target": {"kind": "Asset", "id": asset_id},
        "category": "Wear",
        "severity": "Caution",
        "text": "hexapod stalls below 0.5 mm/s",
        "workaround": "run at 0.6 mm/s",
        "tags": ["motion", "low-speed"],
    }
    body.update(overrides)
    response = client.post("/cautions", json=body)
    assert response.status_code == 201, response.text
    return str(response.json()["caution_id"]), body


@pytest.mark.contract
def test_get_cautions_returns_200_with_full_state() -> None:
    with TestClient(create_app()) as client:
        cid, seeded = _seed(client)
        response = client.get(f"/cautions/{cid}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == cid
    assert body["target"] == seeded["target"]
    assert body["category"] == "Wear"
    assert body["severity"] == "Caution"
    assert body["text"] == "hexapod stalls below 0.5 mm/s"
    assert body["workaround"] == "run at 0.6 mm/s"
    assert body["tags"] == sorted(["motion", "low-speed"])
    assert body["status"] == "Active"
    assert body["parent_id"] is None
    assert body["superseded_by_caution_id"] is None
    assert body["retired_reason"] is None
    assert body["expires_at"] is None
    assert body["propagate_to_children"] is False


@pytest.mark.contract
def test_get_cautions_returns_404_when_not_found() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/cautions/{uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_get_cautions_returns_422_for_malformed_uuid_path_param() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/cautions/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_reflects_retired_state_after_retire() -> None:
    with TestClient(create_app()) as client:
        cid, _ = _seed(client)
        retire = client.post(f"/cautions/{cid}/retire", json={"reason": "Resolved"})
        assert retire.status_code == 204
        response = client.get(f"/cautions/{cid}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Retired"
    assert body["retired_reason"] == "Resolved"


@pytest.mark.contract
def test_get_cautions_reflects_superseded_state_after_supersede() -> None:
    with TestClient(create_app()) as client:
        asset_id = str(uuid4())
        register = client.post(
            "/cautions",
            json={
                "target": {"kind": "Asset", "id": asset_id},
                "category": "Wear",
                "severity": "Caution",
                "text": "orig",
                "workaround": "orig",
            },
        )
        parent_id = register.json()["caution_id"]
        supersede = client.post(
            f"/cautions/{parent_id}/supersede",
            json={
                "target": {"kind": "Asset", "id": asset_id},
                "category": "Wear",
                "severity": "Caution",
                "text": "amended",
                "workaround": "amended workaround",
            },
        )
        child_id = supersede.json()["caution_id"]

        parent_response = client.get(f"/cautions/{parent_id}")
        child_response = client.get(f"/cautions/{child_id}")

    parent = parent_response.json()
    assert parent["status"] == "Superseded"
    assert parent["superseded_by_caution_id"] == child_id

    child = child_response.json()
    assert child["status"] == "Active"
    assert child["parent_id"] == parent_id


@pytest.mark.contract
def test_get_cautions_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_get_caution_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/cautions/{uuid4()}")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
