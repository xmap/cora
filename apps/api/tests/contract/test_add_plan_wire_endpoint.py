"""Contract tests for `POST /plans/{plan_id}/add-wire`.

Action endpoint with body `{source_asset_id, source_port_name,
target_asset_id, target_port_name}`. Strict validation: direction,
signal_type, port-existence, fan-in, asset-binding. Mirrors
`test_add_asset_port_endpoint.py` (5h) shape.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def _setup_plan_with_two_assets_and_ports(client: TestClient) -> dict[str, Any]:
    _cap_id = create_capability_via_api(client)
    """Seed: 2 Assets each with one OUTPUT + one INPUT port, then a Plan
    binding both. Returns dict with plan_id, src_asset_id, tgt_asset_id."""
    cap_id = client.post("/families", json={"name": "Trigger", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "Test Method",
            "capability_id": _cap_id,
            "needed_family_ids": [cap_id],
        },
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
    # Add ports to source: OUTPUT trigger_out
    client.post(
        f"/assets/{src_asset_id}/add-port",
        json={
            "port_name": "trigger_out",
            "direction": "Output",
            "signal_type": "TTL",
        },
    )
    # Add ports to target: INPUT trigger_in
    client.post(
        f"/assets/{tgt_asset_id}/add-port",
        json={
            "port_name": "trigger_in",
            "direction": "Input",
            "signal_type": "TTL",
        },
    )
    plan_id: str = client.post(
        "/plans",
        json={
            "name": "32-ID Triggered Acquisition",
            "practice_id": practice_id,
            "asset_ids": [src_asset_id, tgt_asset_id],
        },
    ).json()["plan_id"]
    return {
        "plan_id": plan_id,
        "src_asset_id": src_asset_id,
        "tgt_asset_id": tgt_asset_id,
    }


@pytest.mark.contract
def test_post_add_plan_wire_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        ctx = _setup_plan_with_two_assets_and_ports(client)
        response = client.post(
            f"/plans/{ctx['plan_id']}/add-wire",
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
def test_post_add_plan_wire_returns_409_on_duplicate_add() -> None:
    """Strict-not-idempotent: re-adding the same wire returns 409."""
    with TestClient(create_app()) as client:
        ctx = _setup_plan_with_two_assets_and_ports(client)
        body = {
            "source_asset_id": ctx["src_asset_id"],
            "source_port_name": "trigger_out",
            "target_asset_id": ctx["tgt_asset_id"],
            "target_port_name": "trigger_in",
        }
        first = client.post(f"/plans/{ctx['plan_id']}/add-wire", json=body)
        assert first.status_code == 204
        second = client.post(f"/plans/{ctx['plan_id']}/add-wire", json=body)
    assert second.status_code == 409
    assert "already" in second.json()["detail"].lower()


@pytest.mark.contract
def test_post_add_plan_wire_returns_409_on_fan_in_attempt() -> None:
    """Fan-in forbidden: a target port can be wired by at most one source.
    Add a second source asset with its own OUTPUT port, then try to wire
    BOTH sources into the same target port — second attempt 409s."""
    with TestClient(create_app()) as client:
        ctx = _setup_plan_with_two_assets_and_ports(client)
        # Add a SECOND source-capable asset to the Plan
        second_src_id = client.post(
            "/assets",
            json={"name": "PandABox2", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
        ).json()["asset_id"]
        cap_id = client.post("/families", json={"name": "Trigger2", "affordances": []}).json()[
            "family_id"
        ]
        client.post(f"/assets/{second_src_id}/add-family", json={"family_id": cap_id})
        client.post(
            f"/assets/{second_src_id}/add-port",
            json={
                "port_name": "trigger_out",
                "direction": "Output",
                "signal_type": "TTL",
            },
        )
        # NOTE: this second source asset isn't bound to the Plan, so we
        # cannot test fan-in across DIFFERENT plan-bound assets in this
        # contract test (would require redefining the Plan). Instead we
        # exercise fan-in via a self-loop pattern: wire src_asset's
        # trigger_out to tgt_asset's trigger_in twice (same source) which
        # is duplicate-add (caught above), OR add a SECOND port on the
        # source and wire IT to the same target port:
        client.post(
            f"/assets/{ctx['src_asset_id']}/add-port",
            json={
                "port_name": "trigger_out_b",
                "direction": "Output",
                "signal_type": "TTL",
            },
        )
        # First wire (trigger_out -> trigger_in)
        first = client.post(
            f"/plans/{ctx['plan_id']}/add-wire",
            json={
                "source_asset_id": ctx["src_asset_id"],
                "source_port_name": "trigger_out",
                "target_asset_id": ctx["tgt_asset_id"],
                "target_port_name": "trigger_in",
            },
        )
        assert first.status_code == 204, first.text
        # Second wire (trigger_out_b -> SAME trigger_in) should 409
        second = client.post(
            f"/plans/{ctx['plan_id']}/add-wire",
            json={
                "source_asset_id": ctx["src_asset_id"],
                "source_port_name": "trigger_out_b",
                "target_asset_id": ctx["tgt_asset_id"],
                "target_port_name": "trigger_in",
            },
        )
    assert second.status_code == 409
    assert "fan-in" in second.json()["detail"].lower()


@pytest.mark.contract
def test_post_add_plan_wire_returns_409_on_direction_mismatch() -> None:
    """Source port must be OUTPUT; using an INPUT port as source returns 409."""
    with TestClient(create_app()) as client:
        ctx = _setup_plan_with_two_assets_and_ports(client)
        # The source-asset already has trigger_out (OUTPUT); add an INPUT
        # port and try to use IT as the source.
        client.post(
            f"/assets/{ctx['src_asset_id']}/add-port",
            json={
                "port_name": "actually_input",
                "direction": "Input",
                "signal_type": "TTL",
            },
        )
        response = client.post(
            f"/plans/{ctx['plan_id']}/add-wire",
            json={
                "source_asset_id": ctx["src_asset_id"],
                "source_port_name": "actually_input",
                "target_asset_id": ctx["tgt_asset_id"],
                "target_port_name": "trigger_in",
            },
        )
    assert response.status_code == 409
    assert "output" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_add_plan_wire_returns_409_on_signal_type_mismatch() -> None:
    """Source and target signal_type must match exactly."""
    with TestClient(create_app()) as client:
        ctx = _setup_plan_with_two_assets_and_ports(client)
        # Add a target port with DIFFERENT signal_type
        client.post(
            f"/assets/{ctx['tgt_asset_id']}/add-port",
            json={
                "port_name": "lvds_in",
                "direction": "Input",
                "signal_type": "LVDS",
            },
        )
        response = client.post(
            f"/plans/{ctx['plan_id']}/add-wire",
            json={
                "source_asset_id": ctx["src_asset_id"],
                "source_port_name": "trigger_out",
                "target_asset_id": ctx["tgt_asset_id"],
                "target_port_name": "lvds_in",
            },
        )
    assert response.status_code == 409
    assert "signal_type" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_add_plan_wire_returns_409_on_missing_port() -> None:
    """Strict forward-reference: wire a port that doesn't exist yet -> 409."""
    with TestClient(create_app()) as client:
        ctx = _setup_plan_with_two_assets_and_ports(client)
        response = client.post(
            f"/plans/{ctx['plan_id']}/add-wire",
            json={
                "source_asset_id": ctx["src_asset_id"],
                "source_port_name": "nonexistent_out",
                "target_asset_id": ctx["tgt_asset_id"],
                "target_port_name": "trigger_in",
            },
        )
    assert response.status_code == 409
    assert "don't exist" in response.json()["detail"].lower() or (
        "not exist" in response.json()["detail"].lower()
    )


@pytest.mark.contract
def test_post_add_plan_wire_returns_404_for_unknown_plan() -> None:
    with TestClient(create_app()) as client:
        unknown_plan = uuid4()
        response = client.post(
            f"/plans/{unknown_plan}/add-wire",
            json={
                "source_asset_id": str(uuid4()),
                "source_port_name": "x",
                "target_asset_id": str(uuid4()),
                "target_port_name": "y",
            },
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_plan_wire_returns_422_for_malformed_path() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/plans/not-a-uuid/add-wire",
            json={
                "source_asset_id": str(uuid4()),
                "source_port_name": "x",
                "target_asset_id": str(uuid4()),
                "target_port_name": "y",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_plan_wire_returns_422_for_missing_field() -> None:
    with TestClient(create_app()) as client:
        ctx = _setup_plan_with_two_assets_and_ports(client)
        response = client.post(
            f"/plans/{ctx['plan_id']}/add-wire",
            json={
                "source_asset_id": ctx["src_asset_id"],
                "source_port_name": "trigger_out",
                # target_asset_id missing
                "target_port_name": "trigger_in",
            },
        )
    assert response.status_code == 422
