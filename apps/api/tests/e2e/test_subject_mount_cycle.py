"""E2E smoke: subject mount + dismount cycle.

Spans Subject + Equipment BCs end-to-end: register subject, register
+activate asset, attach a capability, mount the subject, GET to
verify `mounted_on_asset_id` is populated, dismount, GET to verify
the field is cleared and status returns to Received.
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_mount_then_dismount_clears_mounted_on_asset_id(
    e2e_client: AsyncClient,
) -> None:
    cap = await e2e_client.post("/families", json={"name": "Tomography", "affordances": []})
    assert cap.status_code == 201
    family_id = UUID(cap.json()["family_id"])

    asset = await e2e_client.post(
        "/assets",
        json={"name": "Goniometer-1", "tier": "Unit", "parent_id": str(uuid4())},
    )
    assert asset.status_code == 201
    asset_id = UUID(asset.json()["asset_id"])

    add_cap = await e2e_client.post(
        f"/assets/{asset_id}/add-family",
        json={"family_id": str(family_id)},
    )
    assert add_cap.status_code == 204

    activate = await e2e_client.post(f"/assets/{asset_id}/activate")
    assert activate.status_code == 204

    subject = await e2e_client.post("/subjects", json={"name": "Sample-A1"})
    assert subject.status_code == 201
    subject_id = UUID(subject.json()["subject_id"])

    mount = await e2e_client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": str(asset_id), "reason": "load for scan"},
    )
    assert mount.status_code == 204

    mounted = await e2e_client.get(f"/subjects/{subject_id}")
    assert mounted.status_code == 200
    body = mounted.json()
    assert body["status"] == "Mounted"
    assert body["mounted_on_asset_id"] == str(asset_id)

    dismount = await e2e_client.post(
        f"/subjects/{subject_id}/dismount",
        json={"reason": "scan complete"},
    )
    assert dismount.status_code == 204

    after = await e2e_client.get(f"/subjects/{subject_id}")
    assert after.status_code == 200
    after_body = after.json()
    assert after_body["status"] == "Received"
    assert after_body["mounted_on_asset_id"] is None
