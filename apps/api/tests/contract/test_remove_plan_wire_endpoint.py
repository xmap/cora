"""Contract tests for `POST /plans/{plan_id}/remove-wire`.

Mirror of `test_add_plan_wire_endpoint.py`. Strict-not-idempotent
removal: the Wire must currently exist in the Plan's wire set.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def _setup_plan_with_one_wire(client: TestClient) -> dict[str, Any]:
    _cap_id = create_capability_via_api(client)
    """Seed a Plan with two Assets, one OUTPUT port + one INPUT port, and
    add one Wire connecting them. Returns plan_id, src/tgt asset ids."""
    cap_id = client.post("/families", json={"name": "Trigger", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={"name": "Test Method", "capability_id": _cap_id, "needed_family_ids": [cap_id]},
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    src_asset_id = client.post(
        "/assets",
        json={"name": "PandABox", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    tgt_asset_id = client.post(
        "/assets",
        json={"name": "Camera", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    for asset_id in (src_asset_id, tgt_asset_id):
        client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    client.post(
        f"/assets/{src_asset_id}/add-port",
        json={"port_name": "trigger_out", "direction": "Output", "signal_type": "TTL"},
    )
    client.post(
        f"/assets/{tgt_asset_id}/add-port",
        json={"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
    )
    plan_id: str = client.post(
        "/plans",
        json={
            "name": "32-ID Triggered Acquisition",
            "practice_id": practice_id,
            "asset_ids": [src_asset_id, tgt_asset_id],
        },
    ).json()["plan_id"]
    add_resp = client.post(
        f"/plans/{plan_id}/add-wire",
        json={
            "source_asset_id": src_asset_id,
            "source_port_name": "trigger_out",
            "target_asset_id": tgt_asset_id,
            "target_port_name": "trigger_in",
        },
    )
    assert add_resp.status_code == 204, add_resp.text
    return {
        "plan_id": plan_id,
        "src_asset_id": src_asset_id,
        "tgt_asset_id": tgt_asset_id,
    }


@pytest.mark.contract
def test_post_remove_plan_wire_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        ctx = _setup_plan_with_one_wire(client)
        response = client.post(
            f"/plans/{ctx['plan_id']}/remove-wire",
            json={
                "source_asset_id": ctx["src_asset_id"],
                "source_port_name": "trigger_out",
                "target_asset_id": ctx["tgt_asset_id"],
                "target_port_name": "trigger_in",
            },
        )
    assert response.status_code == 204, response.text
    assert response.content == b""


@pytest.mark.contract
def test_post_remove_plan_wire_returns_404_on_absent_wire() -> None:
    """Strict-not-idempotent: removing a wire that's not currently in
    the set returns 404."""
    with TestClient(create_app()) as client:
        ctx = _setup_plan_with_one_wire(client)
        # Try to remove a wire whose target_port_name doesn't match any.
        response = client.post(
            f"/plans/{ctx['plan_id']}/remove-wire",
            json={
                "source_asset_id": ctx["src_asset_id"],
                "source_port_name": "trigger_out",
                "target_asset_id": ctx["tgt_asset_id"],
                "target_port_name": "different_port",
            },
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_remove_plan_wire_returns_404_for_unknown_plan() -> None:
    with TestClient(create_app()) as client:
        unknown_plan = uuid4()
        response = client.post(
            f"/plans/{unknown_plan}/remove-wire",
            json={
                "source_asset_id": str(uuid4()),
                "source_port_name": "x",
                "target_asset_id": str(uuid4()),
                "target_port_name": "y",
            },
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_remove_plan_wire_returns_422_for_malformed_path() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/plans/not-a-uuid/remove-wire",
            json={
                "source_asset_id": str(uuid4()),
                "source_port_name": "x",
                "target_asset_id": str(uuid4()),
                "target_port_name": "y",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_remove_then_re_add_succeeds() -> None:
    """Add → Remove → Add: the same wire can be re-added after removal."""
    with TestClient(create_app()) as client:
        ctx = _setup_plan_with_one_wire(client)
        body = {
            "source_asset_id": ctx["src_asset_id"],
            "source_port_name": "trigger_out",
            "target_asset_id": ctx["tgt_asset_id"],
            "target_port_name": "trigger_in",
        }
        remove_resp = client.post(f"/plans/{ctx['plan_id']}/remove-wire", json=body)
        assert remove_resp.status_code == 204
        re_add_resp = client.post(f"/plans/{ctx['plan_id']}/add-wire", json=body)
    assert re_add_resp.status_code == 204
