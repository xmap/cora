"""End-to-end proof: the Diffractometer Assembly materializes as a Fixture,
and the register_fixture affordance-union gate (Watch Item 10) fires.

The Diffractometer is the catalog Assembly that presents the Positioner
Role by COMPOSING a Goniometer (sample circles + x/y/z), zero-or-more
RotaryStage detector-arm circles, and a reciprocal-space PseudoAxis. It is
fleet-attested (4-ID, 8-ID and ~9 more) but had never been materialized as
a Fixture -- so the affordance-union check on a presents_as Assembly had
never actually run on a real composed instrument (the existing Microscope
fixture tests use an Assembly with empty presents_as, which SKIPS the gate).

This is that first exercise. The gate requires:

    union(constituent Families' affordances) >= Positioner.required_affordances

Positioner requires {Homeable, Limitable}; the Goniometer carries them, so
the union covers the contract and the fixture registers (201). The negative
case seeds the Goniometer WITHOUT those affordances, so the union no longer
covers Positioner and register_fixture returns 409
(FixtureCannotPresentRoleError).

The in-memory RoleLookup / FamilyLookup are seeded with the real seeded
contract values (the projection worker does not run in the `test` app
environment), keyed by the deterministic role_stream_id / family_stream_id
so the ids match what bootstrap wrote at boot.
"""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.role import RoleName, role_stream_id

pytestmark = pytest.mark.contract

_POSITIONER_ID = role_stream_id(RoleName("Positioner"))
_GONIOMETER_ID = family_stream_id(FamilyName("Goniometer"))
_ROTARYSTAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_PSEUDOAXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

# The seeded Goniometer affordance set (Pass 2 added Translatable).
_GONIOMETER_AFFORDANCES = ["Homeable", "Limitable", "Rotatable", "Translatable"]


def _seed_lookups(app: FastAPI, *, goniometer_covers_positioner: bool = True) -> None:
    """Mirror the seeded Positioner Role + constituent Families into the
    in-memory lookups. When goniometer_covers_positioner is False the
    Goniometer is seeded WITHOUT Homeable/Limitable, so the constituent
    union no longer covers Positioner's required set and the gate fires."""
    app.state.deps.role_lookup.register(
        role_id=_POSITIONER_ID,
        name="Positioner",
        required_affordances=["Homeable", "Limitable"],
    )
    app.state.deps.family_lookup.register(
        family_id=_GONIOMETER_ID,
        name="Goniometer",
        affordances=_GONIOMETER_AFFORDANCES if goniometer_covers_positioner else ["Rotatable"],
        presents_as=[_POSITIONER_ID],
    )
    app.state.deps.family_lookup.register(
        family_id=_ROTARYSTAGE_ID,
        name="RotaryStage",
        affordances=["Homeable", "Limitable", "Rotatable", "Following", "Marking"],
        presents_as=[_POSITIONER_ID],
    )
    app.state.deps.family_lookup.register(
        family_id=_PSEUDOAXIS_ID,
        name="PseudoAxis",
        affordances=[],
        presents_as=[],
    )


def _register_asset(client: TestClient, name: str, family_id: UUID) -> str:
    asset_id = client.post(
        "/assets",
        json={"name": name, "tier": "Device", "parent_id": str(uuid4())},
    ).json()["asset_id"]
    r = client.post(f"/assets/{asset_id}/add-family", json={"family_id": str(family_id)})
    assert r.status_code == 204, r.text
    return asset_id


def _define_diffractometer_assembly(client: TestClient) -> str:
    """Define the composed Diffractometer, presenting the seeded Positioner
    Role, with the three catalog slots (goniometer / detector_arm /
    reciprocal_space)."""
    body = {
        "name": "Diffractometer",
        "presents_as": [str(_POSITIONER_ID)],
        "required_slots": [
            {
                "slot_name": "goniometer",
                "required_family_ids": [str(_GONIOMETER_ID)],
                "cardinality": "Exactly1",
            },
            {
                "slot_name": "detector_arm",
                "required_family_ids": [str(_ROTARYSTAGE_ID)],
                "cardinality": "ZeroOrMore",
            },
            {
                "slot_name": "reciprocal_space",
                "required_family_ids": [str(_PSEUDOAXIS_ID)],
                "cardinality": "Exactly1",
            },
        ],
        "required_wires": [],
    }
    r = client.post("/assemblies", json=body)
    assert r.status_code == 201, r.text
    return r.json()["assembly_id"]


def _bindings(gonio: str, arm: str, recip: str) -> list[dict[str, str]]:
    return [
        {"slot_name": "goniometer", "asset_id": gonio},
        {"slot_name": "detector_arm", "asset_id": arm},
        {"slot_name": "reciprocal_space", "asset_id": recip},
    ]


def test_diffractometer_fixture_registers_when_constituents_cover_positioner() -> None:
    """Happy path: a Goniometer (covers Homeable+Limitable) + a detector-arm
    RotaryStage + a reciprocal-space PseudoAxis materialize the composed
    Diffractometer. The affordance-union gate passes because the constituent
    union covers Positioner's required set."""
    app = create_app()
    with TestClient(app) as client:
        _seed_lookups(app)
        assembly_id = _define_diffractometer_assembly(client)
        gonio = _register_asset(client, "SampleCircles", _GONIOMETER_ID)
        arm = _register_asset(client, "DetectorArm", _ROTARYSTAGE_ID)
        recip = _register_asset(client, "HklAxis", _PSEUDOAXIS_ID)
        resp = client.post(
            f"/assemblies/{assembly_id}/fixtures",
            json={"slot_asset_bindings": _bindings(gonio, arm, recip), "parameter_overrides": {}},
        )
    assert resp.status_code == 201, resp.text
    UUID(resp.json()["fixture_id"])


def test_diffractometer_fixture_rejected_when_no_constituent_covers_positioner() -> None:
    """The gate fires: with the Goniometer seeded without Homeable/Limitable
    and NO detector-arm RotaryStage bound (detector_arm is ZeroOrMore), the
    union of every bound constituent's affordances is short of Positioner's
    required set, so the Diffractometer cannot present Positioner and
    register_fixture returns 409 (FixtureCannotPresentRoleError). First time
    the Watch-Item-10 gate rejects a real composed instrument.

    Note the gate's semantics: the affordance union is taken across ALL
    bound constituents, so a Positioner-presenting Diffractometer is
    satisfied when ANY bound part supplies the required affordances (in the
    happy path the Goniometer does; a bound detector-arm RotaryStage would
    also suffice). Rejection requires that NO constituent supplies them,
    which is why the RotaryStage arm is omitted here."""
    app = create_app()
    with TestClient(app) as client:
        _seed_lookups(app, goniometer_covers_positioner=False)
        assembly_id = _define_diffractometer_assembly(client)
        gonio = _register_asset(client, "SampleCircles", _GONIOMETER_ID)
        recip = _register_asset(client, "HklAxis", _PSEUDOAXIS_ID)
        resp = client.post(
            f"/assemblies/{assembly_id}/fixtures",
            json={
                "slot_asset_bindings": [
                    {"slot_name": "goniometer", "asset_id": gonio},
                    {"slot_name": "reciprocal_space", "asset_id": recip},
                ],
                "parameter_overrides": {},
            },
        )
    assert resp.status_code == 409, resp.text
