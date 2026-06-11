"""2-BM facility install (Unit + Devices + Trust shape).

cluster: Seed
archetype: setup
bc_primary: Equipment
bc_touches: Access, Equipment, Trust

Scenario test that exercises `install_aps_unit` end-to-end and asserts
the full 2-BM facility-level state lands. Parallel to
`test_aps_facility.py` for APS-Site level — this scenario is the
source-of-truth for the Unit-level install ceremony shared by every
`test_2bm_*` scenario.

See [[project_pilot_docs_design]] for the phase / file-naming taxonomy
this scenario fits into.

## Coverage

  - **Access BC**: 3 human operator Actors (operator pool: 2-BM Operator
    1/2/3 with canonical fixture-owned UUIDs) + 2 review-chain reviewer
    Actors (2-BM Beamline Scientist + APS Experiment Safety Review Board)
  - **Equipment BC**: 2-BM (Unit, facility-anchored root) + 2 Devices
    (rotary + linear motor, with Capabilities)
  - **Trust BC**: 2-BM Zone + 2-BM Local Conduit (self-loop) + 2 Policies
    (Operations + Agent). The Agent Policy permits `RUN_DEBRIEF_ACTOR_ID`
    even though no Agent aggregate is registered here — Run Debrief lives
    at facility scope (registered by `test_aps_facility.py`), and Trust
    BC has no command-time referential integrity, so a forward-permitted
    principal is fine.

## What this test does NOT cover

Recipe / Operation / Run / Dataset / Campaign / Subject state is
beamline-scenario territory — handled by each `test_2bm_*` scenario.
This install scenario stops at facility shape.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.access.aggregates.actor import ActorKind, load_actor
from cora.trust.aggregates.conduit import load_conduit
from cora.trust.aggregates.policy import load_policy
from cora.trust.aggregates.zone import load_zone
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import (
    BEAMLINE_SCIENTIST_ACTOR_ID,
    BM2_AGENT_POLICY_ID,
    BM2_LOCAL_CONDUIT_ID,
    BM2_OPERATIONS_POLICY_ID,
    BM2_ZONE_ID,
    ESRB_ACTOR_ID,
    OPERATOR_POOL_IDS,
    RUN_DEBRIEF_ACTOR_ID,
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
)

_NOW = datetime(2026, 5, 17, 9, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000002f00bb")

# Asset hierarchy: scenario-supplied UUIDs per the fixture convention.
# Mnemonic hex: 2f00 prefix = "2-BM facility install"; trailing kind tag
# matches the rest of the corpus (a=unit/device, c=capability).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-0000002f00a1")

_CAP_ROTARY_STAGE_ID = UUID("01900000-0000-7000-8000-0000002f00c1")
_CAP_LINEAR_STAGE_ID = UUID("01900000-0000-7000-8000-0000002f00c2")
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-0000002f00a2")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-0000002f00a3")

_DEVICES = (
    DeviceSpec(
        "Aerotech_ABRS_rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID
    ),
    DeviceSpec("Sample_top_X", _ASSET_SAMPLE_TOP_X_ID, "LinearStage", _CAP_LINEAR_STAGE_ID),
)


@pytest.mark.integration
async def test_2bm_facility_install_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Run the canonical 2-BM facility install and assert every aggregate
    landed on its stream — operators, Asset hierarchy, Trust shape."""
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=facility_id_prefix(
            unit_id=_2BM_UNIT_ID,
            devices=_DEVICES,
        ),
    )

    result = await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- FacilityIds: canonical fixture-owned + scenario-supplied -----
    assert result.operator_pool_ids == OPERATOR_POOL_IDS
    assert result.beamline_scientist_actor_id == BEAMLINE_SCIENTIST_ACTOR_ID
    assert result.esrb_actor_id == ESRB_ACTOR_ID
    assert result.unit_id == _2BM_UNIT_ID
    assert result.bm2_zone_id == BM2_ZONE_ID
    assert result.bm2_local_conduit_id == BM2_LOCAL_CONDUIT_ID
    assert result.bm2_operations_policy_id == BM2_OPERATIONS_POLICY_ID
    assert result.bm2_agent_policy_id == BM2_AGENT_POLICY_ID

    # ----- Access BC: 3 named human operators -----
    # Names live in actor_profile (PII vault); dedicated tests cover that
    # contract. Here we pin the aggregate-level identity + kind.
    for actor_id in OPERATOR_POOL_IDS:
        actor = await load_actor(deps.event_store, actor_id)
        assert actor is not None
        assert actor.kind is ActorKind.HUMAN

    # ----- Access BC: 2 review-chain reviewer Actors -----
    bs_actor = await load_actor(deps.event_store, BEAMLINE_SCIENTIST_ACTOR_ID)
    assert bs_actor is not None
    assert bs_actor.kind is ActorKind.HUMAN

    esrb_actor = await load_actor(deps.event_store, ESRB_ACTOR_ID)
    assert esrb_actor is not None
    assert esrb_actor.kind is ActorKind.HUMAN

    # ----- Equipment BC: Asset stream versions reflect register + add_family -----
    _, unit_version = await deps.event_store.load("Asset", _2BM_UNIT_ID)
    assert unit_version == 1
    # Devices: register_asset (v1) + add_asset_family (v2)
    _, aerotech_version = await deps.event_store.load("Asset", _ASSET_AEROTECH_ABRS_ID)
    assert aerotech_version == 2

    # ----- Trust BC: Zone + Conduit + 2 Policies -----
    zone = await load_zone(deps.event_store, BM2_ZONE_ID)
    assert zone is not None
    assert zone.name.value == "2-BM Zone"

    conduit = await load_conduit(deps.event_store, BM2_LOCAL_CONDUIT_ID)
    assert conduit is not None
    assert conduit.name.value == "2-BM Local Conduit"
    assert conduit.source_zone_id == BM2_ZONE_ID  # self-loop
    assert conduit.target_zone_id == BM2_ZONE_ID

    ops_policy = await load_policy(deps.event_store, BM2_OPERATIONS_POLICY_ID)
    assert ops_policy is not None
    assert ops_policy.name.value == "2-BM Operations Policy"
    assert ops_policy.conduit_id == BM2_LOCAL_CONDUIT_ID
    assert ops_policy.permitted_principal_ids == frozenset(OPERATOR_POOL_IDS)
    assert "ActivateAsset" in ops_policy.permitted_commands  # representative

    agent_policy = await load_policy(deps.event_store, BM2_AGENT_POLICY_ID)
    assert agent_policy is not None
    assert agent_policy.name.value == "2-BM Agent Policy"
    assert agent_policy.conduit_id == BM2_LOCAL_CONDUIT_ID
    assert agent_policy.permitted_principal_ids == frozenset({RUN_DEBRIEF_ACTOR_ID})
    assert "RegisterDecision" in agent_policy.permitted_commands  # representative
