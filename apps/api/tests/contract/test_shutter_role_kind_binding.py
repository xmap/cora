"""Proof: the shutter-commanding Methods bind the seeded Shutter Role.

Closes the loop on coining the Shutter Role -- dark_field / flat_field /
xpcs were exactly the three Methods whose rule-of-three earned it, so
this shows the Role is actually bindable, not a tag. Uses the REAL seeded
Shutter Role + Shutter Family ids (via role_stream_id / family_stream_id),
matching what bootstrap wrote at boot.

xpcs is the richest case: fully Role-bound (Detector + Shutter +
Controller), the first Method with no anatomical family_id binding at all.
"""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.role import RoleName, role_stream_id
from tests.contract._helpers import create_capability_via_api

pytestmark = pytest.mark.contract

_DETECTOR_ID = role_stream_id(RoleName("Detector"))
_SHUTTER_ROLE_ID = role_stream_id(RoleName("Shutter"))
_CONTROLLER_ID = role_stream_id(RoleName("Controller"))
_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_SHUTTER_FAMILY_ID = family_stream_id(FamilyName("Shutter"))
_TIMINGCONTROLLER_ID = family_stream_id(FamilyName("TimingController"))


def _seed_lookups(app: FastAPI, *, shutter_presents_role: bool = True) -> None:
    """Seed the Roles + Families xpcs binds, with the real seeded contract
    values. When shutter_presents_role is False the Shutter Family is
    seeded WITHOUT the Shutter Role so its slot fails satisfaction."""
    app.state.deps.role_lookup.register(
        role_id=_DETECTOR_ID, name="Detector", required_affordances=["Imageable"]
    )
    app.state.deps.role_lookup.register(
        role_id=_SHUTTER_ROLE_ID, name="Shutter", required_affordances=["Shutterable"]
    )
    app.state.deps.role_lookup.register(
        role_id=_CONTROLLER_ID, name="Controller", required_affordances=["Identifiable"]
    )
    app.state.deps.family_lookup.register(
        family_id=_CAMERA_ID,
        name="Camera",
        affordances=["Imageable", "Binnable", "Coolable", "Triggerable", "Streamable", "Recording"],
        presents_as=[_DETECTOR_ID],
    )
    app.state.deps.family_lookup.register(
        family_id=_SHUTTER_FAMILY_ID,
        name="Shutter",
        affordances=["Shutterable"],
        presents_as=[_SHUTTER_ROLE_ID] if shutter_presents_role else [],
    )
    app.state.deps.family_lookup.register(
        family_id=_TIMINGCONTROLLER_ID,
        name="TimingController",
        affordances=["Identifiable", "Pulsing", "Reportable"],
        presents_as=[_CONTROLLER_ID],
    )


def _register_asset(client: TestClient, name: str, family_id: UUID) -> str:
    asset_id = client.post(
        "/assets",
        json={"name": name, "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    r = client.post(f"/assets/{asset_id}/add-family", json={"family_id": str(family_id)})
    assert r.status_code == 204, r.text
    return asset_id


def _author_xpcs_method(client: TestClient) -> str:
    """Author xpcs with three role_kind slots: detector + shutter + controller."""
    cap_id = create_capability_via_api(client)
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "Xpcs",
            "capability_id": cap_id,
            "needed_family_ids": [],
        },
    ).json()["method_id"]
    for role_name, role_id in (
        ("detector", _DETECTOR_ID),
        ("shutter", _SHUTTER_ROLE_ID),
        ("timing", _CONTROLLER_ID),
    ):
        r = client.post(
            f"/methods/{method_id}/add-required-role",
            json={
                "requirement": {
                    "role_name": role_name,
                    "role_kind": str(role_id),
                    "required_ports": [],
                    "optional": False,
                }
            },
        )
        assert r.status_code == 201, r.text
    return method_id


def _plan_over(client: TestClient, method_id: str, asset_ids: list[str]) -> str:
    practice_id = client.post(
        "/practices",
        json={"name": "XpcsPractice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    return client.post(
        "/plans",
        json={"name": "XpcsPlan", "practice_id": practice_id, "asset_ids": asset_ids},
    ).json()["plan_id"]


def test_xpcs_binds_detector_shutter_controller_roles() -> None:
    """Happy path: a Camera (Detector) + a Shutter (Shutter Role) + a
    TimingController (Controller) satisfy the three role_kind slots. xpcs
    is fully Role-bound, with no anatomical family_id binding."""
    app = create_app()
    with TestClient(app) as client:
        _seed_lookups(app)
        method_id = _author_xpcs_method(client)
        camera = _register_asset(client, "CoherentCam", _CAMERA_ID)
        shutter = _register_asset(client, "FastShutter", _SHUTTER_FAMILY_ID)
        timing = _register_asset(client, "SoftGlue", _TIMINGCONTROLLER_ID)
        plan_id = _plan_over(client, method_id, [camera, shutter, timing])
        for role_name, asset_id in (
            ("detector", camera),
            ("shutter", shutter),
            ("timing", timing),
        ):
            resp = client.post(
                f"/plans/{plan_id}/bind-role",
                json={"role_name": role_name, "asset_id": asset_id},
            )
            assert resp.status_code == 201, f"{role_name}: {resp.text}"


def test_xpcs_shutter_slot_rejects_asset_not_presenting_shutter_role() -> None:
    """The gate fires on the just-coined Shutter Role: a Shutter Family
    seeded without the Shutter Role cannot satisfy the shutter slot -> 409.
    Proves the Role is a live binding contract, not a tag."""
    app = create_app()
    with TestClient(app) as client:
        _seed_lookups(app, shutter_presents_role=False)
        method_id = _author_xpcs_method(client)
        shutter = _register_asset(client, "FastShutter", _SHUTTER_FAMILY_ID)
        plan_id = _plan_over(client, method_id, [shutter])
        resp = client.post(
            f"/plans/{plan_id}/bind-role",
            json={"role_name": "shutter", "asset_id": shutter},
        )
    assert resp.status_code == 409, resp.text
