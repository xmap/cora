"""End-to-end proof: the tomography Method binds by seeded Role, not by family.

This exercises the affordance/role machinery on the ACTUAL seeded
vocabulary (Positioner + Detector, the real SEED_ROLES / SEED_FAMILIES
ids), not synthetic hand-authored roles. It is the payoff of the seed
work: an authored Method (`tomography`) declares its needs as
`role_kind` RoleRequirements, and a Plan satisfies them through
`Family.presents_as` + the affordance-cover gate.

Shape mirrors the catalog `tomography` entry: two Positioner slots (the
tomographic rotation axis + the sample x/y/z stack) and one Detector
slot. The Scintillator deliberately does NOT appear -- it is a
constituent of a composed detector Assembly, not a Method requirement, so
binding by the Detector Role drops it from the contract (the de-mirroring
Pass-1 surfaced).

The in-memory RoleLookup / FamilyLookup are seeded with the real seeded
contract values (the projection worker does not run in the `test` app
environment), keyed by the deterministic `role_stream_id` /
`family_stream_id` so the ids match what `bootstrap_families` /
`bootstrap_equipment` wrote to the event store at boot.
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

_POSITIONER_ID = role_stream_id(RoleName("Positioner"))
_DETECTOR_ID = role_stream_id(RoleName("Detector"))
_ROTARYSTAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_LINEARSTAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAMERA_ID = family_stream_id(FamilyName("Camera"))


def _seed_lookups(app: FastAPI, *, camera_presents_detector: bool = True) -> None:
    """Mirror the seeded Role/Family contract into the in-memory lookups.

    Values match SEED_ROLES / SEED_FAMILIES: Positioner requires
    {Homeable, Limitable}; Detector requires {Imageable}. RotaryStage /
    LinearStage present Positioner; Camera presents Detector. When
    `camera_presents_detector` is False, Camera is seeded WITHOUT the
    Detector Role so the Detector-slot bind fails the satisfaction check.
    """
    app.state.deps.role_lookup.register(
        role_id=_POSITIONER_ID,
        name="Positioner",
        required_affordances=["Homeable", "Limitable"],
    )
    app.state.deps.role_lookup.register(
        role_id=_DETECTOR_ID,
        name="Detector",
        required_affordances=["Imageable"],
    )
    app.state.deps.family_lookup.register(
        family_id=_ROTARYSTAGE_ID,
        name="RotaryStage",
        affordances=["Homeable", "Limitable", "Rotatable", "Following", "Marking"],
        presents_as=[_POSITIONER_ID],
    )
    app.state.deps.family_lookup.register(
        family_id=_LINEARSTAGE_ID,
        name="LinearStage",
        affordances=["Homeable", "Limitable", "Translatable"],
        presents_as=[_POSITIONER_ID],
    )
    app.state.deps.family_lookup.register(
        family_id=_CAMERA_ID,
        name="Camera",
        affordances=["Imageable", "Binnable", "Coolable", "Triggerable", "Streamable", "Recording"],
        presents_as=[_DETECTOR_ID] if camera_presents_detector else [],
    )


def _register_asset(client: TestClient, name: str, family_id: UUID) -> str:
    asset_id = client.post(
        "/assets",
        json={"name": name, "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    r = client.post(f"/assets/{asset_id}/add-family", json={"family_id": str(family_id)})
    assert r.status_code == 204, r.text
    return asset_id


def _author_tomography_method(client: TestClient) -> str:
    """Author the tomography Method with role_kind RoleRequirements:
    two Positioner slots (rotation + sample stack) and one Detector slot."""
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
    for role_name, role_id in (
        ("rotation", _POSITIONER_ID),
        ("sample_stack", _POSITIONER_ID),
        ("detector", _DETECTOR_ID),
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
        json={"name": "TomoPractice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    return client.post(
        "/plans",
        json={"name": "TomoPlan", "practice_id": practice_id, "asset_ids": asset_ids},
    ).json()["plan_id"]


def test_tomography_binds_seeded_positioner_and_detector_roles() -> None:
    """The happy path: a rotation RotaryStage + a sample LinearStage (both
    present Positioner) + a Camera (presents Detector) satisfy the three
    role_kind slots. Proves the seeded vocabulary binds end-to-end."""
    app = create_app()
    with TestClient(app) as client:
        _seed_lookups(app)
        method_id = _author_tomography_method(client)
        rotation = _register_asset(client, "MainRotary", _ROTARYSTAGE_ID)
        sample = _register_asset(client, "SampleXYZ", _LINEARSTAGE_ID)
        camera = _register_asset(client, "TomoCam", _CAMERA_ID)
        plan_id = _plan_over(client, method_id, [rotation, sample, camera])

        for role_name, asset_id in (
            ("rotation", rotation),
            ("sample_stack", sample),
            ("detector", camera),
        ):
            resp = client.post(
                f"/plans/{plan_id}/bind-role",
                json={"role_name": role_name, "asset_id": asset_id},
            )
            assert resp.status_code == 201, f"{role_name}: {resp.text}"


def test_tomography_detector_slot_rejects_asset_not_presenting_detector() -> None:
    """The gate fires: a Camera seeded WITHOUT the Detector Role cannot
    satisfy the detector slot -> 409. Proves the affordance/presents_as
    satisfaction check is live on seeded vocabulary, not bypassed."""
    app = create_app()
    with TestClient(app) as client:
        _seed_lookups(app, camera_presents_detector=False)
        method_id = _author_tomography_method(client)
        camera = _register_asset(client, "TomoCam", _CAMERA_ID)
        plan_id = _plan_over(client, method_id, [camera])
        resp = client.post(
            f"/plans/{plan_id}/bind-role",
            json={"role_name": "detector", "asset_id": camera},
        )
    assert resp.status_code == 409, resp.text
