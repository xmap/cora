"""Sample-tower deployment at APS 2-BM (Assembly + Fixture + containment).

cluster: Commissioning
archetype: setup
bc_primary: Equipment
bc_touches: Equipment

Models the 2-BM sample tower as ONE `SampleTower` Assembly presenting as
the seeded `Positioner` Role, materialized by ONE Fixture binding the
installed stack, with the kinematic stacking order carried on the
orthogonal containment axis (`Asset.parent_id`, a literal-deep chain).

The tower is a single installed stack, bottom to top:

    SampleTable (4-DOF translation base, on the hutch floor / Unit)
      -> Hexapod              (6-DOF coarse pose)
        -> LaminographyPitch  (Kohzu goniometer; tilt setpoint = lamino vs tomo)
          -> Rotary           (theta air-bearing rotation)
            -> SampleTop_X     (co-rotates with theta)
              -> SampleTop_Z   (co-rotates with theta)

The experiment-vs-loadout boundary is the load-bearing rule: tomography,
laminography, and mosaic are all Recipe Methods/Plans over this ONE
Fixture, NOT separate Fixtures. Laminography is a tilt SETPOINT on the
permanently-installed LaminographyPitch stage (operator-confirmed), not a
hardware insert/remove, so it is a Plan parameter and earns no second
Fixture. A second Fixture is reserved for a real hardware EXCHANGE (a
rotary swap), which 2-BM does not run as a live loadout variant today.

The fixed laminography wedge is a passive part (no slot/Asset here), and
the hexapod's six DoF facets (PseudoAxis) are out of scope for this
structure scenario; both are deferred to follow-ups.

## register_fixture install precondition

register_fixture rejects a binding whose Asset is not currently installed
in some Mount. `install_existing_asset_into_fresh_mount` gives each bound
constituent a lightweight Mount (activate + Frame + Mount + install +
drain on its own id pool) so the precondition passes; the containment
chain is the orthogonal axis and is asserted separately.

## Naming

The tilt stage binds the NEW `TiltStage` Family (a goniometer is a
rotational, limited-range stage; reusing `RotaryStage` would falsely
attribute its Following/Marking PSO affordances, and `LinearStage` is
wrong for a rotation). The base table binds the `Table` Family (not
`OpticalTable`, which repeats the OpticalHousing->Housing trap). Families
are defined here with empty affordances per the structure-scenario
convention; the real affordance sets live in the deployment descriptor.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.assembly import (
    SlotCardinality,
    SlotName,
    TemplateSlot,
    load_assembly,
)
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.aggregates.role import SEED_ROLE_POSITIONER_ID
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.attach_asset_to_fixture import AttachAssetToFixture
from cora.equipment.features.attach_asset_to_fixture import bind as bind_attach_asset_to_fixture
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_assembly import bind as bind_define_assembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.equipment.features.register_fixture import RegisterFixture
from cora.equipment.features.register_fixture import bind as bind_register_fixture
from cora.infrastructure.adapters.in_memory_role_lookup import InMemoryRoleLookup
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from tests.integration._equipment_helpers import install_existing_asset_into_fresh_mount
from tests.integration._helpers import (
    build_postgres_deps,
    make_pg_profile_store,
    seed_capability_postgres,
)
from tests.integration.scenarios._facility_fixture import (
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000430bb")

# Facility hierarchy (scenario tag 430).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000430a01")

# Family ids (deterministic uuid5 from the name).
_FAM_TABLE = family_stream_id(FamilyName("Table"))
_FAM_HEXAPOD = family_stream_id(FamilyName("Hexapod"))
_FAM_TILT_STAGE = family_stream_id(FamilyName("TiltStage"))
_FAM_ROTARY_STAGE = family_stream_id(FamilyName("RotaryStage"))
_FAM_LINEAR_STAGE = family_stream_id(FamilyName("LinearStage"))

# Recipe ladder (TOWER-3: a positioning Method binds the tower as a unit).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000430501")
_CAPABILITY_RECIPE_ID = UUID("01900000-0000-7000-8000-000000c0430e")


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue: the facility prefix for a device-less Unit
    install, then a generous block of anonymous ids. The tower Assets are
    registered fresh (ids captured from handler returns), and the
    per-constituent Mount choreography runs on its own pool inside the
    helper, so the tail only needs to be long enough."""
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=()),
        *[uuid4() for _ in range(200)],
    ]


@pytest.mark.integration
async def test_sample_tower_deployment_plays_out_end_to_end(db_pool: asyncpg.Pool) -> None:
    """Compose the 2-BM sample tower as ONE SampleTower Assembly + ONE
    Fixture end-to-end: Unit install, NEW Families, the six stack Assets
    in a literal-deep parent_id chain, per-constituent Mount/install, the
    Assembly presenting as the Positioner Role, the Fixture binding the
    5-slot stack (sample_top is OneOrMore), and the attaches. Assert the
    Assembly/Fixture streams, the containment chain, and the fixture_id
    back-references."""
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(SEED_ROLE_POSITIONER_ID, "Positioner")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue(), role_lookup=role_lookup)

    # ----- Facility install: just the 2-BM Unit + Trust shape (no devices;
    #       the tower Assets are registered fresh below with their chain). -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=(),
    )

    # ----- NEW Families (empty affordances; real sets live in the descriptor) -----
    for name in ("Table", "Hexapod", "TiltStage", "RotaryStage", "LinearStage"):
        await bind_define_family(deps)(
            DefineFamily(name=name, affordances=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- The six stack Assets, registered bottom-to-top with each one's
    #       parent_id set to the stage directly below (literal-deep chain).
    #       The base table parents to the 2-BM Unit. -----
    tower: dict[str, UUID] = {}
    parent = _2BM_UNIT_ID
    for key, asset_name, fam_id in (
        ("table", "SampleTable", _FAM_TABLE),
        ("coarse_pose", "Hexapod", _FAM_HEXAPOD),
        ("tilt", "LaminographyPitch", _FAM_TILT_STAGE),
        ("rotation", "Rotary", _FAM_ROTARY_STAGE),
        ("sample_top_x", "SampleTop_X", _FAM_LINEAR_STAGE),
        ("sample_top_z", "SampleTop_Z", _FAM_LINEAR_STAGE),
    ):
        aid = await bind_register_asset(deps)(
            RegisterAsset(name=asset_name, tier=AssetTier.DEVICE, parent_id=parent),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        tower[key] = aid
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=aid, family_id=fam_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        parent = aid  # next stage rides on this one

    # ----- SampleTower Assembly: presents as the Positioner Role; one slot
    #       per stack element, sample_top is OneOrMore (binds X + Z). No
    #       sub-assemblies, no required wires (the lamino pitch-tracks-theta
    #       coupling is a conduct-time PseudoAxis/Plan concern, not a
    #       template wire). -----
    def _slot(
        name: str, fam_id: UUID, cardinality: SlotCardinality = SlotCardinality.EXACTLY_1
    ) -> TemplateSlot:
        return TemplateSlot(
            slot_name=SlotName(name),
            required_family_ids=frozenset({fam_id}),
            cardinality=cardinality,
        )

    tower_id = await bind_define_assembly(deps)(
        DefineAssembly(
            name="SampleTower",
            presents_as=frozenset({SEED_ROLE_POSITIONER_ID}),
            required_slots=frozenset(
                {
                    _slot("table", _FAM_TABLE),
                    _slot("coarse_pose", _FAM_HEXAPOD),
                    _slot("tilt", _FAM_TILT_STAGE),
                    _slot("rotation", _FAM_ROTARY_STAGE),
                    _slot("sample_top", _FAM_LINEAR_STAGE, SlotCardinality.ONE_OR_MORE),
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    tower_assembly = await load_assembly(deps.event_store, tower_id)
    assert tower_assembly is not None
    assert tower_assembly.content_hash is not None

    # ----- Install every bound constituent in a lightweight Mount so
    #       register_fixture's install precondition passes. -----
    # slot_name -> asset_id as a LIST: the two sample-tops both bind the
    # single OneOrMore `sample_top` slot, so that name repeats.
    bound: list[tuple[str, UUID]] = [
        ("table", tower["table"]),
        ("coarse_pose", tower["coarse_pose"]),
        ("tilt", tower["tilt"]),
        ("rotation", tower["rotation"]),
        ("sample_top", tower["sample_top_x"]),
        ("sample_top", tower["sample_top_z"]),
    ]
    for i, (slot_name, asset_id) in enumerate(bound):
        await install_existing_asset_into_fresh_mount(
            db_pool, now=_NOW, asset_id=asset_id, slot_code=f"sample_tower_{slot_name}_{i}"
        )

    # ----- Register the SampleTower Fixture (binds the 5-slot stack) -----
    fixture_id = await bind_register_fixture(deps)(
        RegisterFixture(
            assembly_id=tower_id,
            slot_asset_bindings=frozenset(
                SlotAssetBinding(slot_name=slot_name, asset_id=asset_id)
                for slot_name, asset_id in bound
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Attach each bound Asset (sets its fixture_id back-reference) -----
    for _, asset_id in bound:
        await bind_attach_asset_to_fixture(deps)(
            AttachAssetToFixture(asset_id=asset_id, fixture_id=fixture_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Minimal Recipe ladder (TOWER-3): a positioning Method binds the
    #       tower as a UNIT. The Positioner-Role capability comes from the
    #       SampleTower Assembly's presents_as, declared via needed_assembly_ids;
    #       needed_family_ids names the asset-level axes the bound constituents
    #       directly provide. The Plan binds the stack's asset_ids, no wires. -----
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_RECIPE_ID,
        code="cora.capability.sample_positioning",
        name="SamplePositioning",
    )
    method_id = await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_RECIPE_ID,
            name="sample_tower_positioning",
            needed_family_ids=frozenset({_FAM_ROTARY_STAGE, _FAM_LINEAR_STAGE}),
            needed_assembly_ids=frozenset({tower_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await bind_define_practice(deps)(
        DefinePractice(name="2BM_sample_tower_practice", method_id=method_id, site_id=_APS_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_sample_tower_plan",
            practice_id=practice_id,
            asset_ids=frozenset(asset_id for _, asset_id in bound),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ===== Assertions =====

    # SampleTower stream: AssemblyDefined with 5 leaf slots, no sub-assemblies,
    # presenting as the Positioner Role (the scalar presenter Family is gone).
    tower_events, _ = await deps.event_store.load("Assembly", tower_id)
    assert [e.event_type for e in tower_events] == ["AssemblyDefined"]
    payload = tower_events[0].payload
    assert len(payload["required_slots"]) == 5
    assert payload["required_sub_assemblies"] == []
    assert payload["presents_as"] == [str(SEED_ROLE_POSITIONER_ID)]

    # Fixture stream: FixtureRegistered binding 6 Assets across 5 slot names
    # (the `sample_top` OneOrMore slot carries 2 of the 6 bindings).
    fixture_events, _ = await deps.event_store.load("Fixture", fixture_id)
    assert [e.event_type for e in fixture_events] == ["FixtureRegistered"]
    bindings = fixture_events[0].payload["slot_asset_bindings"]
    assert len(bindings) == 6
    assert {b["slot_name"] for b in bindings} == {
        "table",
        "coarse_pose",
        "tilt",
        "rotation",
        "sample_top",
    }
    assert sum(1 for b in bindings if b["slot_name"] == "sample_top") == 2
    # Exact slot -> asset mapping (self-documenting; the register_fixture
    # family-match guard backstops it today, but pin it so a future wider-Family
    # change cannot silently mis-bind).
    assert {(b["slot_name"], b["asset_id"]) for b in bindings} == {
        (slot_name, str(asset_id)) for slot_name, asset_id in bound
    }
    # Boundary lock (experiment-vs-loadout): the Fixture records the INSTALLED
    # STACK only. tomography / laminography / mosaic are Recipe Methods/Plans
    # over this ONE Fixture, never baked into it, so no scan-strategy override
    # may leak into the Fixture. This is the design's mandated negative guard.
    assert fixture_events[0].payload["parameter_overrides"] == {}

    # Containment: the literal-deep chain. Each stage's parent is the stage
    # below; the base table's parent is the 2-BM Unit. parent_id is set at
    # registration, so it lives on the AssetRegistered (events[0]) payload.
    expected_parent = {
        "table": _2BM_UNIT_ID,
        "coarse_pose": tower["table"],
        "tilt": tower["coarse_pose"],
        "rotation": tower["tilt"],
        "sample_top_x": tower["rotation"],
        "sample_top_z": tower["sample_top_x"],
    }
    for key, asset_id in tower.items():
        events, _ = await deps.event_store.load("Asset", asset_id)
        assert events[0].event_type == "AssetRegistered"
        assert events[0].payload["parent_id"] == str(expected_parent[key]), (
            f"{key}: expected parent {expected_parent[key]}"
        )

    # Each bound Asset carries AssetAttachedToFixture pointing at THIS Fixture
    # (verify the back-reference value, not just that an attach happened).
    for slot_name, asset_id in bound:
        events, _ = await deps.event_store.load("Asset", asset_id)
        attaches = [e for e in events if e.event_type == "AssetAttachedToFixture"]
        assert attaches, f"{slot_name}: expected fixture attach"
        assert attaches[-1].payload["fixture_id"] == str(fixture_id), (
            f"{slot_name}: attached to the wrong fixture"
        )

    # TOWER-3: the positioning Method requires the tower as a UNIT -- it names
    # the SampleTower Assembly via needed_assembly_ids, and that Assembly's
    # presents_as carries the Positioner Role (the unit-level contract).
    method_events, _ = await deps.event_store.load("Method", method_id)
    assert str(tower_id) in method_events[0].payload["needed_assembly_ids"]

    # Plan binds the stack asset_ids directly, with no wires.
    plan_events, _ = await deps.event_store.load("Plan", plan_id)
    assert not [e for e in plan_events if e.event_type == "PlanWireAdded"]
