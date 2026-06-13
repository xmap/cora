"""APS facility hierarchy (Argonne + APS).

cluster: Seed
archetype: setup
bc_primary: Equipment
bc_touches: Access, Agent, Caution, Equipment, Recipe, Safety, Supply

Scenario test for the facility-install rhythm: register the Enterprise
+ Site Asset hierarchy and seed the BCs whose aggregates naturally
hang at those levels (Actor, Agent, Practice with site_id=APS,
Clearance, Supply, Caution). Pre-beam; no beamline-level state.

See [[project_pilot_docs_design]] for the phase / file-naming taxonomy
this scenario fits into.

## Coverage

  - **Equipment BC**: Argonne (Enterprise) + APS (Site, parent=Argonne)
    + Sector 2 (Area, parent=APS). APS organizes beamlines into
    sectors; Sector 2 hosts the operational 2-BM beamline. Sector 35
    (the planned 2-BM pilot) is intentionally absent until its Unit
    lands.
  - **Access BC**: one Actor (kind=human) for use as principal
  - **Agent BC**: one Agent (RunDebriefer), cross-BC-co-registers a
    second Actor with kind=agent
  - **Recipe BC**: one Method + one Practice with site_id=APS
  - **Safety BC**: one Clearance issued at APS
  - **Supply BC**: one facility-scope Supply
  - **Caution BC**: one Caution targeting the APS Site Asset

## What this test does NOT cover

Beamline-level state (Plan, Procedure, Subject, Run, Dataset,
Campaign) belongs to per-beamline scenarios. Cross-scenario
composition (a beamline scenario consuming this one's APS Site id) is
a future refactor: extract a shared facility-setup fixture once a
second beamline scenario lands.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access.aggregates.actor import ActorKind, load_actor
from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.agent.aggregates.agent import AgentStatus, ModelRef, load_agent
from cora.agent.features.define_agent import DefineAgent
from cora.agent.features.define_agent import bind as bind_define_agent
from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionSeverity,
)
from cora.caution.features.register_caution import RegisterCaution
from cora.caution.features.register_caution import bind as bind_register_caution
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from cora.safety.aggregates.clearance import (
    AssetBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features.register_clearance import RegisterClearance
from cora.safety.features.register_clearance import bind as bind_register_clearance
from cora.supply.features.register_supply import RegisterSupply
from cora.supply.features.register_supply import bind as bind_register_supply
from tests.integration._helpers import (
    build_postgres_deps,
    make_pg_profile_store,
    seed_capability_postgres,
)
from tests.integration.scenarios._facility_fixture import RUN_DEBRIEF_ACTOR_ID

_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000a05000")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000a050bb")

# Pre-allocated aggregate ids. Order matters in _id_queue (FixedIdGenerator
# consumes head-first). Mnemonic hex tags in the last segment: e=enterprise,
# 5=site, 7=area (sector), a=actor, c=capability, d=recipe (method/practice),
# 8=clearance, 9=supply, f=caution.
_ARGONNE_ENTERPRISE_ID = UUID("01900000-0000-7000-8000-000000a00e01")
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000a00501")
_SECTOR_2_AREA_ID = UUID("01900000-0000-7000-8000-000000a00701")
_ACTOR_OPERATOR_ID = UUID("01900000-0000-7000-8000-000000a00a01")
_CAP_PROBE_GENERIC_ID = family_stream_id(FamilyName("ProbeGeneric"))
_METHOD_DARK_BASELINE_ID = UUID("01900000-0000-7000-8000-000000a00d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0ed79")
_PRACTICE_DARK_BASELINE_APS_ID = UUID("01900000-0000-7000-8000-000000a00d11")
_CLEARANCE_ESAF_ID = UUID("01900000-0000-7000-8000-000000a00801")
_SUPPLY_HELIUM_ID = UUID("01900000-0000-7000-8000-000000a00901")
_CAUTION_TOPOFF_ID = UUID("01900000-0000-7000-8000-000000a00f01")


def _id_queue() -> list[UUID]:
    """Pre-allocated id queue for FixedIdGenerator (head-first consumption).

    Each block annotates which command consumes which ids: aggregate id
    first, then one event id per emitted event. Cross-BC writes
    (define_agent) emit two events on two streams in one transaction.
    """
    e = uuid4
    return [
        # register_asset Argonne (Enterprise, parent=None): asset_id, event_id
        _ARGONNE_ENTERPRISE_ID,
        e(),
        # register_asset APS (Site, parent=Argonne): asset_id, event_id
        _APS_SITE_ID,
        e(),
        # register_asset Sector 2 (Area, parent=APS): asset_id, event_id
        _SECTOR_2_AREA_ID,
        e(),
        # register_actor (operator, human): actor_id, event_id
        _ACTOR_OPERATOR_ID,
        e(),
        # define_agent (RunDebriefer, kind=agent): shared_id, actor_event_id, agent_event_id
        # Cross-BC atomic write: ActorRegistered + AgentDefined in one transaction.
        # Canonical RUN_DEBRIEF_ACTOR_ID (from _facility_fixture) so the 2-BM
        # Agent Policy registered by `install_aps_unit` references the same UUID.
        RUN_DEBRIEF_ACTOR_ID,  # shared agent_id == actor_id
        e(),  # ActorRegistered event id
        e(),  # AgentDefined event id
        # define_family (generic Probe, for Method to declare): event_id only
        # (stream id is now derived from the name, not popped)
        e(),
        # define_method (dark_baseline): method_id, event_id
        _METHOD_DARK_BASELINE_ID,
        e(),
        # define_practice (APS dark-baseline practice, site_id=APS): practice_id, event_id
        _PRACTICE_DARK_BASELINE_APS_ID,
        e(),
        # register_clearance (APS ESAF): clearance_id, event_id
        _CLEARANCE_ESAF_ID,
        e(),
        # register_supply (facility helium): supply_id, event_id
        _SUPPLY_HELIUM_ID,
        e(),
        # register_caution (facility top-up notice): caution_id, event_id
        _CAUTION_TOPOFF_ID,
        e(),
    ]


@pytest.mark.integration
async def test_facility_install_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Register Argonne Enterprise + APS Site + the facility-level BCs
    that hang at those levels. Each registration grounds one inventory
    page under `docs/deployments/argonne/` or `docs/deployments/aps/`.
    """
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Equipment BC: Enterprise + Site Assets -----

    await bind_register_asset(deps)(
        RegisterAsset(name="Argonne", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register_asset(deps)(
        RegisterAsset(name="APS", tier=AssetTier.UNIT, parent_id=_ARGONNE_ENTERPRISE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register_asset(deps)(
        RegisterAsset(name="Sector 2", tier=AssetTier.COMPONENT, parent_id=_APS_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Access BC: register one human Actor (the operator principal) -----

    await bind_register_actor(deps, profile_store=make_pg_profile_store(db_pool))(
        RegisterActor(name="APS Operator"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Agent BC: define one Agent (cross-BC: co-registers a kind=agent Actor) -----

    agent_id = await bind_define_agent(deps, profile_store=make_pg_profile_store(db_pool))(
        DefineAgent(
            kind="RunDebriefer",
            name="Run Debrief",
            version="v1",
            model_ref=ModelRef(
                provider="anthropic",
                model="claude-sonnet-4-6",
                snapshot_pin="20251001",
            ),
            description="Synthesises terminal Runs into AAR-shaped debriefs.",
            capabilities=frozenset({"summarize"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Recipe BC: Method + Practice (Practice.site_id = APS Site Asset) -----

    await bind_define_family(deps)(
        DefineFamily(name="ProbeGeneric", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.acquisition",
        name="Acquisition",
    )
    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="dark_baseline",
            needed_family_ids=frozenset({_CAP_PROBE_GENERIC_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="APS_standard_dark_baseline_practice",
            method_id=_METHOD_DARK_BASELINE_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Safety BC: one Clearance issued at APS -----

    # Seed the in-memory ClearanceTemplateLookup with an Active "ESAF"
    # template in the "cora" facility so the handler's cross-aggregate
    # template lookup resolves before the decider runs. (Integration
    # tests using build_postgres_deps directly do not trigger the
    # lifespan auto-seed that ships templates per Active facility.)
    _esaf_template_id: ClearanceTemplateId = ClearanceTemplateId(
        clearance_template_stream_id("cora", "ESAF")
    )
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=_esaf_template_id,
        facility_code="cora",
        code="ESAF",
        status="Active",
        version=1,
    )
    await bind_register_clearance(deps)(
        RegisterClearance(
            template_id=_esaf_template_id,
            facility_code="cora",
            title="Facility umbrella",
            bindings=frozenset({AssetBinding(asset_id=_APS_SITE_ID)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Supply BC: one facility-scope Supply -----

    await bind_register_supply(deps)(
        RegisterSupply(
            kind="cryogen",
            name="APS liquid helium",
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Caution BC: one facility-wide Caution targeting the APS Site Asset -----

    await bind_register_caution(deps)(
        RegisterCaution(
            target=AssetTarget(asset_id=_APS_SITE_ID),
            category=CautionCategory.OPERATIONAL_WINDOW,
            severity=CautionSeverity.NOTICE,
            text=(
                "Top-up injections cause brief beam-flux transients (~0.5s) "
                "every few minutes. Avoid relying on instantaneous flux for "
                "calibration writes during top-up windows."
            ),
            workaround=(
                "Schedule calibration writes between top-up injections, or "
                "use 5-injection averaged observations."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: each aggregate landed on its event stream -----

    argonne_events, argonne_version = await deps.event_store.load("Asset", _ARGONNE_ENTERPRISE_ID)
    assert argonne_version == 1
    assert [e.event_type for e in argonne_events] == ["AssetRegistered"]

    aps_events, aps_version = await deps.event_store.load("Asset", _APS_SITE_ID)
    assert aps_version == 1
    assert [e.event_type for e in aps_events] == ["AssetRegistered"]

    sector2_events, sector2_version = await deps.event_store.load("Asset", _SECTOR_2_AREA_ID)
    assert sector2_version == 1
    assert [e.event_type for e in sector2_events] == ["AssetRegistered"]
    sector2_payload = sector2_events[0].payload
    assert sector2_payload["tier"] == AssetTier.COMPONENT.value
    assert UUID(sector2_payload["parent_id"]) == _APS_SITE_ID

    operator = await load_actor(deps.event_store, _ACTOR_OPERATOR_ID)
    assert operator is not None
    assert operator.kind is ActorKind.HUMAN

    assert agent_id == RUN_DEBRIEF_ACTOR_ID  # canonical, shared with 2-BM Agent Policy
    agent = await load_agent(deps.event_store, agent_id)
    assert agent is not None
    assert agent.status is AgentStatus.DEFINED
    assert agent.kind.value == "RunDebriefer"

    # Cross-BC: define_agent also wrote an Actor with kind=agent at agent_id.
    agent_actor = await load_actor(deps.event_store, agent_id)
    assert agent_actor is not None
    assert agent_actor.kind is ActorKind.AGENT

    practice_events, practice_version = await deps.event_store.load(
        "Practice", _PRACTICE_DARK_BASELINE_APS_ID
    )
    assert practice_version == 1
    assert [e.event_type for e in practice_events] == ["PracticeDefined"]
    # The Practice's site_id payload references the real APS Site Asset id.
    practice_payload = practice_events[0].payload
    assert UUID(practice_payload["site_id"]) == _APS_SITE_ID

    clearance_events, clearance_version = await deps.event_store.load(
        "Clearance", _CLEARANCE_ESAF_ID
    )
    assert clearance_version == 1
    assert [e.event_type for e in clearance_events] == ["ClearanceRegistered"]

    supply_events, supply_version = await deps.event_store.load("Supply", _SUPPLY_HELIUM_ID)
    assert supply_version == 1
    assert [e.event_type for e in supply_events] == ["SupplyRegistered"]

    caution_events, caution_version = await deps.event_store.load("Caution", _CAUTION_TOPOFF_ID)
    assert caution_version == 1
    assert [e.event_type for e in caution_events] == ["CautionRegistered"]
