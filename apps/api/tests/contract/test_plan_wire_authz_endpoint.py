"""Authorization contract tests for `add_plan_wire` / `remove_plan_wire`.

Both endpoints route Authorize-denied calls to HTTP 403 via Recipe BC's
`_handle_unauthorized` (recipe/routes.py:96-101). The handler-level unit
tests in `tests/unit/recipe/test_plan_wire_slices_handlers.py` already
verify Deny -> UnauthorizedError; these contract tests pin the full
stack: route -> handler -> deps.authz.authorize -> 403 + JSON body.

Uses the same TrustAuthorize-with-policy pattern as
`test_cross_principal_bola.py`: a real policy permits P1 to do every
setup command + AddPlanWire / RemovePlanWire; P2 has no permitted
commands at all and gets 403 on the wire endpoints.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)
from tests.contract._helpers import create_capability_via_api


def _seed_policy(
    app: FastAPI,
    *,
    policy_id: UUID,
    permitted_principal: UUID,
    permitted_commands: frozenset[str],
) -> None:
    """Seed a single PolicyDefined event into the running app's
    in-memory store. Same shape as the BOLA contract test's helper.

    Binds the HTTP Surface so REST commands (arriving on
    SYSTEM_HTTP_SURFACE_ID) strict-match under `evaluate`."""
    event = PolicyDefined(
        policy_id=policy_id,
        name="Plan-wire-authz-test-policy",
        conduit_id=UUID(int=0),
        permitted_principal_ids=(permitted_principal,),
        permitted_commands=tuple(permitted_commands),
        occurred_at=datetime.now(tz=UTC),
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="DefinePolicy",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    asyncio.run(
        app.state.deps.event_store.append("Policy", policy_id, 0, [new_event]),
    )


_PERMITTED_SETUP_COMMANDS: frozenset[str] = frozenset(
    {
        # Setup chain to bring a Plan into being with bound Assets and ports.
        "DefineFamily",
        # so the per-principal authz policy must permit DefineCapability too.
        "DefineCapability",
        "DefineMethod",
        "DefinePractice",
        "RegisterAsset",
        "AddAssetFamily",
        "AddAssetPort",
        "DefinePlan",
        # Wire commands — P1 is permitted to add+remove wires; P2 is not.
        "AddPlanWire",
        "RemovePlanWire",
    }
)


@pytest.fixture
def wire_authz_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, UUID, UUID]]:
    """Spin up an app with `TrustAuthorize` wired against a policy that
    permits ONE principal (P1) to issue every command needed to set up
    a Plan AND to add/remove wires. P2 is any other UUID; the policy
    denies it implicitly.

    Yields (client, p1, p2).
    """
    policy_id = UUID("01900000-0000-7000-8000-00000000d701")
    p1 = UUID("01900000-0000-7000-8000-00000000d711")
    p2 = UUID("01900000-0000-7000-8000-00000000d712")

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))

    client = TestClient(create_app())
    client.__enter__()  # start lifespan; app.state.deps populated

    _seed_policy(
        cast("FastAPI", client.app),
        policy_id=policy_id,
        permitted_principal=p1,
        permitted_commands=_PERMITTED_SETUP_COMMANDS,
    )
    try:
        yield client, p1, p2
    finally:
        client.__exit__(None, None, None)


def _setup_plan_with_two_wired_assets(client: TestClient, principal: UUID) -> dict[str, Any]:
    """Helper: P1 sets up the full Plan + Assets + ports needed to wire."""
    h = {"X-Principal-Id": str(principal)}
    _cap_id = create_capability_via_api(client, headers=h)
    cap_id = client.post(
        "/families", json={"name": "Trigger", "affordances": []}, headers=h
    ).json()["family_id"]
    method_id = client.post(
        "/methods",
        json={"name": "Test Method", "capability_id": _cap_id, "needed_family_ids": [cap_id]},
        headers=h,
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
        headers=h,
    ).json()["practice_id"]
    src_id = client.post(
        "/assets",
        json={
            "name": "PandABox",
            "tier": "Unit",
            "parent_id": None,
            "facility_code": "cora",
        },
        headers=h,
    ).json()["asset_id"]
    tgt_id = client.post(
        "/assets",
        json={
            "name": "Camera",
            "tier": "Unit",
            "parent_id": None,
            "facility_code": "cora",
        },
        headers=h,
    ).json()["asset_id"]
    for asset_id in (src_id, tgt_id):
        client.post(
            f"/assets/{asset_id}/add-family",
            json={"family_id": cap_id},
            headers=h,
        )
    client.post(
        f"/assets/{src_id}/add-port",
        json={
            "port_name": "trigger_out",
            "direction": "Output",
            "signal_type": "TTL",
        },
        headers=h,
    )
    client.post(
        f"/assets/{tgt_id}/add-port",
        json={
            "port_name": "trigger_in",
            "direction": "Input",
            "signal_type": "TTL",
        },
        headers=h,
    )
    plan_id = client.post(
        "/plans",
        json={
            "name": "Triggered Acquisition",
            "practice_id": practice_id,
            "asset_ids": [src_id, tgt_id],
        },
        headers=h,
    ).json()["plan_id"]
    return {"plan_id": plan_id, "src_id": src_id, "tgt_id": tgt_id}


@pytest.mark.contract
def test_p2_gets_403_when_adding_a_wire_to_p1s_plan(
    wire_authz_app: tuple[TestClient, UUID, UUID],
) -> None:
    """Authz contract: P2 is not in `permitted_principal_ids` for AddPlanWire,
    so POST /plans/{id}/add-wire returns 403 before any decider logic
    runs. Pins the full route -> handler -> deps.authz.authorize -> 403 stack."""
    client, p1, p2 = wire_authz_app
    ctx = _setup_plan_with_two_wired_assets(client, p1)

    response = client.post(
        f"/plans/{ctx['plan_id']}/add-wire",
        json={
            "source_asset_id": ctx["src_id"],
            "source_port_name": "trigger_out",
            "target_asset_id": ctx["tgt_id"],
            "target_port_name": "trigger_in",
        },
        headers={"X-Principal-Id": str(p2)},
    )
    assert response.status_code == 403, response.text
    assert "detail" in response.json()


@pytest.mark.contract
def test_p2_gets_403_when_removing_a_wire_from_p1s_plan(
    wire_authz_app: tuple[TestClient, UUID, UUID],
) -> None:
    """Same shape as the add-wire denial: P2 hits 403 on remove_wire too."""
    client, p1, p2 = wire_authz_app
    ctx = _setup_plan_with_two_wired_assets(client, p1)

    # P1 adds a wire so there's something to attempt removing.
    add_resp = client.post(
        f"/plans/{ctx['plan_id']}/add-wire",
        json={
            "source_asset_id": ctx["src_id"],
            "source_port_name": "trigger_out",
            "target_asset_id": ctx["tgt_id"],
            "target_port_name": "trigger_in",
        },
        headers={"X-Principal-Id": str(p1)},
    )
    assert add_resp.status_code == 204, add_resp.text

    # P2 attempts the remove.
    response = client.post(
        f"/plans/{ctx['plan_id']}/remove-wire",
        json={
            "source_asset_id": ctx["src_id"],
            "source_port_name": "trigger_out",
            "target_asset_id": ctx["tgt_id"],
            "target_port_name": "trigger_in",
        },
        headers={"X-Principal-Id": str(p2)},
    )
    assert response.status_code == 403, response.text
    assert "detail" in response.json()


@pytest.mark.contract
def test_p1_can_still_add_and_remove_wires(
    wire_authz_app: tuple[TestClient, UUID, UUID],
) -> None:
    """Inverse sanity: the gate is per-principal, not blanket-deny.
    P1 (permitted) can add and remove wires."""
    client, p1, _ = wire_authz_app
    ctx = _setup_plan_with_two_wired_assets(client, p1)

    add_resp = client.post(
        f"/plans/{ctx['plan_id']}/add-wire",
        json={
            "source_asset_id": ctx["src_id"],
            "source_port_name": "trigger_out",
            "target_asset_id": ctx["tgt_id"],
            "target_port_name": "trigger_in",
        },
        headers={"X-Principal-Id": str(p1)},
    )
    assert add_resp.status_code == 204, add_resp.text

    remove_resp = client.post(
        f"/plans/{ctx['plan_id']}/remove-wire",
        json={
            "source_asset_id": ctx["src_id"],
            "source_port_name": "trigger_out",
            "target_asset_id": ctx["tgt_id"],
            "target_port_name": "trigger_in",
        },
        headers={"X-Principal-Id": str(p1)},
    )
    assert remove_resp.status_code == 204, remove_resp.text
