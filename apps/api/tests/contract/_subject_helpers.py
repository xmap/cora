"""Shared helpers for Subject contract tests that need an Active Asset.

Subject contract tests that mount as setup need an `Active`
`Equipment.Asset` to mount onto (cross-aggregate validation per the
mount_subject decider). This helper registers + activates an Asset
via the public HTTP API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def register_active_asset(client: TestClient, *, name: str = "Goniometer-1") -> str:
    """Register + activate a Unit-tier Asset; return its id.

    Synthetic parent_id (uuid4) is acceptable because the
    Equipment register decider does not pre-validate parent
    existence (eventual-consistency stance).
    """
    response = client.post(
        "/assets",
        json={"name": name, "tier": "Unit", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["asset_id"]
    activated = client.post(f"/assets/{asset_id}/activate")
    assert activated.status_code == 204, activated.text
    return asset_id


__all__ = ["register_active_asset"]
