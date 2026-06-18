"""Contract tests for `POST /plans/{plan_id}/bind-role` and
`POST /plans/{plan_id}/unbind-role`.

Slice 2 of the positional role-tagging workstream. Exercises the
full REST surface: bind / unbind happy paths + 404 / 409 / 422 cases.

Layer 3 sub-slice 3D adds the `role_kind` binding path
(`setup_plan_with_role_kind` + the role_kind test block at the
bottom): the Method's RoleRequirement carries `role_kind` (a global
Role contract id) instead of `family_id`, and the bind succeeds iff
a Family on the Asset advertises that Role via `presents_as` with a
covering affordance set. In the `test` app environment the projection
worker does not run, so the RoleLookup + FamilyLookup in-memory
adapters are seeded directly via `app.state.deps` (same pattern as
the 3E + add_method_required_role contract tests).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def setup_plan_with_role(client: TestClient) -> dict[str, Any]:
    """Seed Capability + Family + Method (with one required role) +
    Asset (carrying the right Family + port) + Plan binding the
    Asset. Returns ids needed for the role-binding calls."""
    cap_id = create_capability_via_api(client)
    family_id = client.post("/families", json={"name": "Camera", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "Tomography",
            "capability_id": cap_id,
            "needed_family_ids": [],
        },
    ).json()["method_id"]
    # Declare a required role on the Method.
    r = client.post(
        f"/methods/{method_id}/add-required-role",
        json={
            "requirement": {
                "role_name": "detector",
                "family_id": family_id,
                "required_ports": [
                    {"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
                ],
                "optional": False,
            }
        },
    )
    assert r.status_code == 201, r.text
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "camera", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": family_id})
    client.post(
        f"/assets/{asset_id}/add-port",
        json={"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
    )
    plan_id = client.post(
        "/plans",
        json={"name": "P1", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    return {
        "plan_id": plan_id,
        "asset_id": asset_id,
        "method_id": method_id,
        "family_id": family_id,
    }


@pytest.mark.contract
def test_post_bind_plan_role_returns_201_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        ctx = setup_plan_with_role(client)
        response = client.post(
            f"/plans/{ctx['plan_id']}/bind-role",
            json={"role_name": "detector", "asset_id": ctx["asset_id"]},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_bind_plan_role_returns_409_on_duplicate_role_name() -> None:
    with TestClient(create_app()) as client:
        ctx = setup_plan_with_role(client)
        first = client.post(
            f"/plans/{ctx['plan_id']}/bind-role",
            json={"role_name": "detector", "asset_id": ctx["asset_id"]},
        )
        assert first.status_code == 201
        second = client.post(
            f"/plans/{ctx['plan_id']}/bind-role",
            json={"role_name": "detector", "asset_id": ctx["asset_id"]},
        )
    assert second.status_code == 409
    assert "already binds role" in second.json()["detail"]


@pytest.mark.contract
def test_post_bind_plan_role_returns_409_for_unknown_role_name() -> None:
    with TestClient(create_app()) as client:
        ctx = setup_plan_with_role(client)
        response = client.post(
            f"/plans/{ctx['plan_id']}/bind-role",
            json={"role_name": "sample_monitor", "asset_id": ctx["asset_id"]},
        )
    assert response.status_code == 409
    assert "not declared" in response.json()["detail"]


@pytest.mark.contract
def test_post_bind_plan_role_returns_409_when_asset_not_bound() -> None:
    with TestClient(create_app()) as client:
        ctx = setup_plan_with_role(client)
        unbound_asset = str(uuid4())
        response = client.post(
            f"/plans/{ctx['plan_id']}/bind-role",
            json={"role_name": "detector", "asset_id": unbound_asset},
        )
    # 404 OR 409 depending on whether asset lookup fails first.
    assert response.status_code in (404, 409)


@pytest.mark.contract
def test_post_bind_plan_role_returns_422_for_invalid_role_name_length() -> None:
    with TestClient(create_app()) as client:
        ctx = setup_plan_with_role(client)
        response = client.post(
            f"/plans/{ctx['plan_id']}/bind-role",
            json={"role_name": "a" * 51, "asset_id": ctx["asset_id"]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_unbind_plan_role_returns_204_after_bind() -> None:
    with TestClient(create_app()) as client:
        ctx = setup_plan_with_role(client)
        bound = client.post(
            f"/plans/{ctx['plan_id']}/bind-role",
            json={"role_name": "detector", "asset_id": ctx["asset_id"]},
        )
        assert bound.status_code == 201
        response = client.post(
            f"/plans/{ctx['plan_id']}/unbind-role",
            json={"role_name": "detector"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_unbind_plan_role_returns_404_for_unknown_role() -> None:
    with TestClient(create_app()) as client:
        ctx = setup_plan_with_role(client)
        response = client.post(
            f"/plans/{ctx['plan_id']}/unbind-role",
            json={"role_name": "detector"},
        )
    assert response.status_code == 404


# ---------- Layer 3 sub-slice 3D: role_kind binding path ----------


def setup_plan_with_role_kind(
    client: TestClient,
    app: FastAPI,
    *,
    family_advertises: bool = True,
) -> dict[str, Any]:
    """Seed the role_kind binding path: a Role + a Family that advertises
    it via presents_as + a Method whose RoleRequirement carries role_kind.

    The RoleLookup + FamilyLookup in-memory adapters are seeded directly
    via app.state.deps because the projection worker does not run in the
    `test` app environment. When `family_advertises` is False the Family
    is registered WITHOUT the Role in its presents_as so the bind hits
    PlanRoleAssetCannotPresentError (409).
    """
    cap_id = create_capability_via_api(client)
    # A non-seed Role name (the 4 SEED_ROLES occupy their own streams).
    role_resp = client.post(
        "/roles",
        json={
            "name": "Diagnostician",
            "docstring": "Acquires 2D image frames.",
            "required_affordances": ["Imageable"],
            "optional_affordances": [],
            "produces": [],
            "consumes": [],
        },
    )
    assert role_resp.status_code == 201, role_resp.text
    role_id = UUID(role_resp.json()["role_id"])
    app.state.deps.role_lookup.register(
        role_id=role_id,
        name="Diagnostician",
        required_affordances=["Imageable"],
    )

    family_id = client.post(
        "/families", json={"name": "Camera", "affordances": ["Imageable"]}
    ).json()["family_id"]
    app.state.deps.family_lookup.register(
        family_id=UUID(family_id),
        name="Camera",
        affordances=["Imageable"],
        presents_as=[role_id] if family_advertises else [],
    )

    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "Tomography",
            "capability_id": cap_id,
            "needed_family_ids": [],
        },
    ).json()["method_id"]
    r = client.post(
        f"/methods/{method_id}/add-required-role",
        json={
            "requirement": {
                "role_name": "imager",
                "role_kind": str(role_id),
                "required_ports": [
                    {"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
                ],
                "optional": False,
            }
        },
    )
    assert r.status_code == 201, r.text
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "camera", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": family_id})
    client.post(
        f"/assets/{asset_id}/add-port",
        json={"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
    )
    plan_id = client.post(
        "/plans",
        json={"name": "P1", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    return {"plan_id": plan_id, "asset_id": asset_id, "role_id": str(role_id)}


@pytest.mark.contract
def test_post_bind_plan_role_kind_returns_201_when_family_advertises_role() -> None:
    app = create_app()
    with TestClient(app) as client:
        ctx = setup_plan_with_role_kind(client, app, family_advertises=True)
        response = client.post(
            f"/plans/{ctx['plan_id']}/bind-role",
            json={"role_name": "imager", "asset_id": ctx["asset_id"]},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_bind_plan_role_kind_returns_409_when_family_does_not_advertise() -> None:
    app = create_app()
    with TestClient(app) as client:
        ctx = setup_plan_with_role_kind(client, app, family_advertises=False)
        response = client.post(
            f"/plans/{ctx['plan_id']}/bind-role",
            json={"role_name": "imager", "asset_id": ctx["asset_id"]},
        )
    assert response.status_code == 409, response.text


@pytest.mark.contract
def test_post_add_required_role_kind_returns_404_when_role_unresolved() -> None:
    """The add_method_required_role handler edge-loads the role_kind via
    RoleLookup; an unseeded role_kind surfaces as 404 at authoring time."""
    with TestClient(create_app()) as client:
        cap_id = create_capability_via_api(client)
        method_id = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "Tomography",
                "capability_id": cap_id,
                "needed_family_ids": [],
            },
        ).json()["method_id"]
        response = client.post(
            f"/methods/{method_id}/add-required-role",
            json={
                "requirement": {
                    "role_name": "imager",
                    "role_kind": "00000000-0000-0000-0000-000000000999",
                    "required_ports": [],
                    "optional": False,
                }
            },
        )
    assert response.status_code == 404, response.text
