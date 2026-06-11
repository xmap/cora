"""Contract tests for `POST /assets/{asset_id}/relocate`.

Action endpoint with a body: `{to_parent_id, reason}`. Covers the
happy path plus each disqualifying-condition error path. Each
guard collapses to a 409 with the diagnostic `reason` string in the
body.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_asset(
    client: TestClient,
    *,
    name: str = "APS-2BM",
    tier: str = "Unit",
    parent_id: str | None = None,
    root: bool = False,
) -> str:
    body: dict[str, str | None] = {
        "name": name,
        "tier": tier,
        "parent_id": parent_id if parent_id is not None else str(uuid4()),
    }
    if root:
        body["parent_id"] = None
        body["facility_code"] = "cora"
    response = client.post("/assets", json=body)
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["asset_id"]
    return asset_id


@pytest.mark.contract
def test_post_relocate_returns_204_on_happy_path() -> None:
    new_parent = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/relocate",
            json={"to_parent_id": new_parent, "reason": "site reorganization"},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_relocate_returns_404_when_asset_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing_id}/relocate",
            json={"to_parent_id": str(uuid4()), "reason": "moved"},
        )
    assert response.status_code == 404
    body = response.json()
    assert missing_id in body["detail"]


@pytest.mark.contract
def test_post_relocate_returns_409_when_asset_is_root() -> None:
    """A root Asset is facility-anchored; cannot have a parent. Diagnostic
    `reason` surfaces the rule in the body."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client, name="ANL", root=True)
        response = client.post(
            f"/assets/{asset_id}/relocate",
            json={"to_parent_id": str(uuid4()), "reason": "moved"},
        )
    assert response.status_code == 409
    assert "Root" in response.json()["detail"]


@pytest.mark.contract
def test_post_relocate_returns_409_when_asset_is_decommissioned() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(
            f"/assets/{asset_id}/relocate",
            json={"to_parent_id": str(uuid4()), "reason": "moved"},
        )
    assert response.status_code == 409
    assert "Decommissioned" in response.json()["detail"]


@pytest.mark.contract
def test_post_relocate_returns_409_for_self_loop() -> None:
    """target_parent_id == asset_id is the trivial cycle case."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/relocate",
            json={"to_parent_id": asset_id, "reason": "moved"},
        )
    assert response.status_code == 409
    assert "self-loop" in response.json()["detail"]


@pytest.mark.contract
def test_post_relocate_returns_409_for_no_op_target_equals_current_parent() -> None:
    """Strict semantics: relocating to the current parent raises 409."""
    parent_id = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client, parent_id=parent_id)
        response = client.post(
            f"/assets/{asset_id}/relocate",
            json={"to_parent_id": parent_id, "reason": "moved"},
        )
    assert response.status_code == 409
    assert "no-op" in response.json()["detail"]


@pytest.mark.contract
def test_post_relocate_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets/not-a-uuid/relocate",
            json={"to_parent_id": str(uuid4()), "reason": "moved"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_relocate_rejects_missing_to_parent_id_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/relocate",
            json={"reason": "moved"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_relocate_rejects_empty_reason_with_422() -> None:
    """Pydantic enforces reason min_length=1 at the API boundary."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/relocate",
            json={"to_parent_id": str(uuid4()), "reason": ""},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_relocate_rejects_oversized_reason_with_422() -> None:
    """Pydantic enforces reason max_length=500 at the API boundary."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/relocate",
            json={"to_parent_id": str(uuid4()), "reason": "x" * 501},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_relocate_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/relocate",
            json={"to_parent_id": str(uuid4()), "reason": "moved"},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204
