"""E2E smoke: define method -> get -> list (projection-backed).

Mirrors `test_actor_lifecycle.py` for the Recipe BC's Method aggregate.
Pinned response shapes: POST returns `{method_id}`, GET returns
`{id, name, needed_family_ids, status, version}`, list returns
`{items: [...], next_cursor}`.
"""

from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_define_then_get_then_list_method(
    e2e_client: AsyncClient,
    e2e_drain: Callable[[], Awaitable[None]],
) -> None:

    cap_post = await e2e_client.post(
        "/capabilities",
        json={
            "code": "cora.capability.e2e.method_lifecycle",
            "name": "E2EMethodLifecycle",
            "required_affordances": [],
            "executor_shapes": ["Method"],
        },
    )
    assert cap_post.status_code == 201
    capability_id = cap_post.json()["capability_id"]

    define = await e2e_client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "XRF Mapping",
            "capability_id": capability_id,
            "needed_family_ids": [],
        },
    )
    assert define.status_code == 201
    method_id = UUID(define.json()["method_id"])

    fetched = await e2e_client.get(f"/methods/{method_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == str(method_id)
    assert body["name"] == "XRF Mapping"
    assert body["status"] == "Defined"
    assert body["needed_family_ids"] == []

    await e2e_drain()
    listed = await e2e_client.get("/methods")
    assert listed.status_code == 200
    page = listed.json()
    assert any(UUID(item["method_id"]) == method_id for item in page["items"])
