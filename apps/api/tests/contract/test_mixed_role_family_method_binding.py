"""Proof: a Method carrying BOTH required_roles and needed_family_ids binds.

The #539 catalog conversions introduced a "mixed" method shape
(single_crystal_diffraction, surface_diffraction, grazing_incidence_scattering,
transmission_xray_microscopy): a positional role slot bound by role_kind
(the area detector -> Detector Role) PLUS a bare needed_family coverage
requirement for a Family that presents no Role (the reciprocal-space
PseudoAxis, or the ZonePlate imaging optic).

These two mechanisms are distinct:
  - required_roles / role_kind: a NAMED positional slot, satisfied by an
    Asset whose Family presents the Role and covers its affordances.
  - needed_family_ids: a bare COVERAGE set, satisfied when the Plan's
    bound Assets collectively include that Family (no positional slot,
    no wire) -- checked at define_plan, PlanFamiliesNotSatisfiedError.

The catalog conversion asserted these coexist on one Method (no XOR).
This proves it at RUNTIME, which the catalog-only #539 commit did not:
the mixed method's Detector role_kind slot binds AND its PseudoAxis
coverage requirement is enforced at plan time.
"""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response

from cora.api.main import create_app
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.role import RoleName, role_stream_id
from tests.contract._helpers import create_capability_via_api

pytestmark = pytest.mark.contract

_DETECTOR_ID = role_stream_id(RoleName("Detector"))
_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_PSEUDOAXIS_ID = family_stream_id(FamilyName("PseudoAxis"))


def _seed_lookups(app: FastAPI) -> None:
    app.state.deps.role_lookup.register(
        role_id=_DETECTOR_ID, name="Detector", required_affordances=["Imageable"]
    )
    app.state.deps.family_lookup.register(
        family_id=_CAMERA_ID,
        name="Camera",
        affordances=["Imageable", "Binnable", "Coolable", "Triggerable", "Streamable", "Recording"],
        presents_as=[_DETECTOR_ID],
    )
    app.state.deps.family_lookup.register(
        family_id=_PSEUDOAXIS_ID, name="PseudoAxis", affordances=[], presents_as=[]
    )


def _register_asset(client: TestClient, name: str, family_id: UUID) -> str:
    asset_id = client.post(
        "/assets",
        json={"name": name, "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    r = client.post(f"/assets/{asset_id}/add-family", json={"family_id": str(family_id)})
    assert r.status_code == 204, r.text
    return asset_id


def _mixed_method(client: TestClient) -> str:
    """single_crystal_diffraction shape: needed_family_ids=[PseudoAxis]
    (bare coverage) + one Detector role_kind slot."""
    cap_id = create_capability_via_api(client)
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "SingleCrystalDiffraction",
            "capability_id": cap_id,
            "needed_family_ids": [str(_PSEUDOAXIS_ID)],
        },
    ).json()["method_id"]
    r = client.post(
        f"/methods/{method_id}/add-required-role",
        json={
            "requirement": {
                "role_name": "detector",
                "role_kind": str(_DETECTOR_ID),
                "required_ports": [],
                "optional": False,
            }
        },
    )
    assert r.status_code == 201, r.text
    return method_id


def _plan(client: TestClient, method_id: str, asset_ids: list[str]) -> Response:
    practice_id = client.post(
        "/practices",
        json={"name": "SxdPractice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    return client.post(
        "/plans",
        json={"name": "SxdPlan", "practice_id": practice_id, "asset_ids": asset_ids},
    )


def test_mixed_method_plan_binds_role_and_covers_needed_family() -> None:
    """Happy path: a Camera (Detector) + a PseudoAxis asset satisfy the
    mixed method -- the Plan is accepted (needed_family coverage holds) and
    the Detector role_kind slot binds."""
    app = create_app()
    with TestClient(app) as client:
        _seed_lookups(app)
        method_id = _mixed_method(client)
        camera = _register_asset(client, "AreaDet", _CAMERA_ID)
        recip = _register_asset(client, "HklAxis", _PSEUDOAXIS_ID)
        plan_resp = _plan(client, method_id, [camera, recip])
        assert plan_resp.status_code == 201, plan_resp.text
        plan_id = plan_resp.json()["plan_id"]
        bind = client.post(
            f"/plans/{plan_id}/bind-role",
            json={"role_name": "detector", "asset_id": camera},
        )
        assert bind.status_code == 201, bind.text


def test_mixed_method_plan_rejected_when_needed_family_absent() -> None:
    """The coverage half fires: a Plan with only the Camera (no PseudoAxis
    asset) fails define_plan because needed_family_ids is not covered,
    even though the Detector role slot could bind. Proves the two
    requirements are independent and both enforced."""
    app = create_app()
    with TestClient(app) as client:
        _seed_lookups(app)
        method_id = _mixed_method(client)
        camera = _register_asset(client, "AreaDet", _CAMERA_ID)
        plan_resp = _plan(client, method_id, [camera])
    assert plan_resp.status_code == 409, plan_resp.text
