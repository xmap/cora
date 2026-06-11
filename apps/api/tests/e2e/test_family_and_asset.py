"""E2E smoke: define family, register asset, attach family.

Exercises the Equipment BC's two create slices plus the cross-aggregate
add_asset_family action endpoint, then GETs the asset to verify the
family appears in its serialized families list.
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_register_asset_then_add_family_round_trips(
    e2e_client: AsyncClient,
) -> None:
    cap_response = await e2e_client.post(
        "/families", json={"name": "Tomography", "affordances": []}
    )
    assert cap_response.status_code == 201
    family_id = UUID(cap_response.json()["family_id"])

    asset_response = await e2e_client.post(
        "/assets",
        json={"name": "APS-2BM", "tier": "Unit", "parent_id": str(uuid4())},
    )
    assert asset_response.status_code == 201
    asset_id = UUID(asset_response.json()["asset_id"])

    add = await e2e_client.post(
        f"/assets/{asset_id}/add-family",
        json={"family_id": str(family_id)},
    )
    assert add.status_code == 204
    assert add.content == b""

    fetched = await e2e_client.get(f"/assets/{asset_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == str(asset_id)
    assert body["family_ids"] == [str(family_id)]
