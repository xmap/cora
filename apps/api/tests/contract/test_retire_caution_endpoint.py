"""Contract tests for `POST /cautions/{caution_id}/retire`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.caution.errors import UnauthorizedError
from cora.caution.features.retire_caution.route import (
    _get_handler as _get_retire_caution_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_body(asset_id: str | None = None) -> dict[str, object]:
    return {
        "target": {"kind": "Asset", "id": asset_id or str(uuid4())},
        "category": "Wear",
        "severity": "Caution",
        "text": "stalls",
        "workaround": "go slower",
    }


def _seed(client: TestClient) -> str:
    response = client.post("/cautions", json=_register_body())
    assert response.status_code == 201
    return str(response.json()["caution_id"])


@pytest.mark.contract
@pytest.mark.parametrize("reason", ["Resolved", "NoLongerApplies", "WrongTarget"])
def test_post_retire_returns_204_on_active_caution(reason: str) -> None:
    with TestClient(create_app()) as client:
        cid = _seed(client)
        response = client.post(f"/cautions/{cid}/retire", json={"reason": reason})
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_retire_returns_404_when_caution_absent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/cautions/{uuid4()}/retire",
            json={"reason": "Resolved"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_retire_returns_409_on_already_retired_caution() -> None:
    with TestClient(create_app()) as client:
        cid = _seed(client)
        first = client.post(f"/cautions/{cid}/retire", json={"reason": "Resolved"})
        assert first.status_code == 204
        second = client.post(f"/cautions/{cid}/retire", json={"reason": "Resolved"})
    assert second.status_code == 409


@pytest.mark.contract
def test_post_retire_returns_422_on_unknown_reason() -> None:
    with TestClient(create_app()) as client:
        cid = _seed(client)
        response = client.post(f"/cautions/{cid}/retire", json={"reason": "MadeUp"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_retire_returns_422_when_reason_missing() -> None:
    with TestClient(create_app()) as client:
        cid = _seed(client)
        response = client.post(f"/cautions/{cid}/retire", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_retire_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_retire_caution_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/cautions/{uuid4()}/retire",
            json={"reason": "Resolved"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
