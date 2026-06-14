"""Shared facility-hierarchy install helper for 2-BM-shape scenario tests.

Extracted when the 3rd scenario re-registered Argonne + APS + 2-BM Unit
by hand (per [[project_pilot_docs_design]] watch item). The install scenario
(`test_aps_facility_*`) is NOT a caller: it IS the source-of-truth
install ceremony being tested, with its own facility-level extras (Agent,
Practice, Clearance, Supply, Caution).

## Two coupled functions

`install_aps_unit()` executes the ceremony; `facility_id_prefix()`
returns the matching `FixedIdGenerator` queue prefix. Callers must use
both together: the prefix MUST sit at the head of `_id_queue()` and the
install call MUST happen before any scenario-specific commands consume
the queue. Drift between the two corrupts every downstream id allocation.

## Operator pool + Reviewer Actors + Trust shape (canonical, fixture-owned)

The fixture owns canonical UUIDs for:

  - **3 human operators** (`OPERATOR_1_ID/OPERATOR_2_ID/OPERATOR_3_ID`),
    matching the 1-3-staff-per-beamline reality. Scenarios pick one via
    `operator_for(__file__)` (round-robin by filename hash) so the same
    human appears as principal across multiple scenarios, exactly the
    way real staff do.
  - **Run Debrief actor id** (`RUN_DEBRIEF_ACTOR_ID`) — the canonical
    identity of the AI agent, shared with `test_aps_facility.py`'s
    `define_agent` call. Lives here so the 2-BM Agent Policy can
    reference it; the actual `Agent` aggregate is only defined in the
    APS facility scenario (Run Debrief subscribes facility-wide, not
    per-beamline).
  - **Review-chain reviewers**:
      - `BEAMLINE_SCIENTIST_ACTOR_ID` (`2-BM Beamline Scientist`) —
        beamline-bound identity, but the role they play in ESAF review
        is facility safety-process work; doc-placed at APS.
      - `ESRB_ACTOR_ID` (`APS Experiment Safety Review Board`) — the
        facility's central safety committee, one identity reused
        across every beamline's ESAFs.
    Both registered here as part of the facility-install ceremony so
    proposal-clearance + Run.start-gate scenarios share one canonical
    Actor.id per reviewer rather than each scenario minting its own.
  - **2-BM Trust shape** (Zone + self-loop Conduit + 2 Policies). The
    Operations Policy permits the 3 human operators on operator-driven
    commands; the Agent Policy permits Run Debrief on decision commands.
    Declarative-only today (`AllowAllAuthorize` is wired for tests); the
    shape grounds the deployment docs and prepares for the eventual
    `Authorize` wiring.

This deviates from the scenario-supplied-UUID pattern used for the Asset
hierarchy (where mnemonic hex tags trace events back to a single
scenario) — operators and Trust artefacts are SHARED identity by design,
so the fixture owns their UUIDs.

## Why scenario-supplied UUIDs (Asset hierarchy)

Each scenario tags its Asset-hierarchy aggregate ids with a mnemonic hex
segment so the event store records remain traceable back to the scenario
that wrote them (for example, `...000000350e01` for Argonne under the
beta-alignment scenario, `...000000352e01` under shakedown). The fixture
must NOT pick canonical UUIDs for Assets; it accepts whatever the caller
declares as constants.

## Usage shape

```python
_DEVICES = (
    DeviceSpec("Rotary", _ASSET_ROTARY_ID, "RotaryStage", _CAP_ROTARY_ID),
    DeviceSpec("SampleTop_X",         _ASSET_LINEAR_ID, "LinearStage", _CAP_LINEAR_ID),
)
_PRINCIPAL_ID = operator_for(__file__)

def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(
            unit_id=_UNIT_ID,
            devices=_DEVICES,
        ),
        # ... scenario-specific ids follow
    ]

async def test_...(db_pool):
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    await install_aps_unit(
        deps,
        correlation_id=_CORRELATION_ID,
        unit_id=_UNIT_ID,
        devices=_DEVICES,
    )
    # ... scenario-specific commands follow, using _PRINCIPAL_ID
```

The beamline Unit is the ROOT Asset: it binds `facility_code`
(default "cora", the seeded self-Facility) and carries `parent_id=None`.
Its Devices nest under the Unit. Site/Area/institution scope is owned
by the Federation Facility aggregate, not by an Asset tier.
"""

import hashlib
import os
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

from cora.access.aggregates.actor import ProfileStore
from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.features.define_conduit import DefineConduit
from cora.trust.features.define_conduit import bind as bind_define_conduit
from cora.trust.features.define_policy import DefinePolicy
from cora.trust.features.define_policy import bind as bind_define_policy
from cora.trust.features.define_zone import DefineZone
from cora.trust.features.define_zone import bind as bind_define_zone

# ---------------------------------------------------------------------------
# Canonical, fixture-owned UUIDs (shared identity across all 2-BM scenarios).
# Mnemonic hex tags in last segment: a=actor (operator pool + reviewers + agent),
# b=trust shape (b01=zone, b02=conduit, b03=ops policy, b04=agent policy).
# ---------------------------------------------------------------------------

OPERATOR_1_ID = UUID("01900000-0000-7000-8000-000000002a01")
OPERATOR_2_ID = UUID("01900000-0000-7000-8000-000000002a02")
OPERATOR_3_ID = UUID("01900000-0000-7000-8000-000000002a03")
OPERATOR_POOL_IDS: tuple[UUID, UUID, UUID] = (OPERATOR_1_ID, OPERATOR_2_ID, OPERATOR_3_ID)
OPERATOR_NAMES: tuple[str, str, str] = ("2-BM Operator 1", "2-BM Operator 2", "2-BM Operator 3")

# Review-chain reviewer Actors. Beamline Scientist is beamline-named because
# each beamline has its own scientist roster, but the role the BS plays in
# ESAF review is APS-scope safety process; the doc inventory row lives at APS.
# ESRB is the facility's central safety committee — one identity facility-wide.
BEAMLINE_SCIENTIST_ACTOR_ID = UUID("01900000-0000-7000-8000-000000002a04")
ESRB_ACTOR_ID = UUID("01900000-0000-7000-8000-000000002a05")
BEAMLINE_SCIENTIST_NAME = "2-BM Beamline Scientist"
ESRB_NAME = "APS Experiment Safety Review Board"

# Canonical Run Debrief actor id. Re-exported alias for the production
# constant `RUN_DEBRIEFER_AGENT_ID` from `cora.agent.seed` (Agent.id ==
# Actor.id per the 8f-a shared-identity invariant, so the fixture's
# Actor-shaped name aliases the Agent-shaped seed constant). The 2-BM
# Agent Policy permits this UUID; the production-boot seed registers
# the Agent at the same UUID; the unit + integration tests reference
# the seed constant directly. Prior to this fix the fixture defined a
# different literal UUID, which silently created two competing
# canonical identities for the RunDebriefer Agent — the Policy would
# have rejected the seeded Agent once Authorize wiring lands.
RUN_DEBRIEF_ACTOR_ID = RUN_DEBRIEFER_AGENT_ID

# 2-BM Trust shape. Self-loop Conduit (source==target==2-BM Zone) because
# the 2-BM scenarios don't yet model cross-zone flows; the Conduit exists
# so the Policies have something to attach to.
BM2_ZONE_ID = UUID("01900000-0000-7000-8000-000000002b01")
BM2_LOCAL_CONDUIT_ID = UUID("01900000-0000-7000-8000-000000002b02")
BM2_OPERATIONS_POLICY_ID = UUID("01900000-0000-7000-8000-000000002b03")
BM2_AGENT_POLICY_ID = UUID("01900000-0000-7000-8000-000000002b04")

# Representative command lists. These do not exhaustively enumerate every
# command an operator / agent ever runs; they document the canonical
# operator-driven vs. agent-driven boundary and will be expanded when
# `Authorize` wiring lands and the policies become enforcement (not just
# documentation) of the seam.
_OPERATIONS_COMMANDS: frozenset[str] = frozenset(
    {
        "ActivateAsset",
        "DegradeAsset",
        "RestoreAsset",
        "AddAssetFamily",
        "RegisterSubject",
        "MountSubject",
        "DismountSubject",
        "DefineMethod",
        "DefinePractice",
        "DefinePlan",
        "RegisterProcedure",
        "StartProcedure",
        "CompleteProcedure",
        "AppendProcedureActivities",
        "StartRun",
        "StopRun",
        "AbortRun",
        "AdjustRun",
        "RegisterDataset",
        "PromoteDataset",
        "RegisterCaution",
        "RegisterClearance",
        "AmendClearance",
        "RegisterSupply",
        "RegisterCampaign",
        "AddRunToCampaign",
    }
)
_AGENT_COMMANDS: frozenset[str] = frozenset(
    {
        "RegisterDecision",
        "RateDecision",
        "AppendInferences",
    }
)


def operator_for(scenario_file: str) -> UUID:
    """Round-robin operator selection by stable hash of the scenario filename.

    Pass `__file__` from the scenario module. Only the basename is hashed
    so moving files between directories doesn't reshuffle assignments.
    Uses blake2b for stability across Python versions (unlike `hash()`,
    which is per-interpreter-run randomized).
    """
    basename = os.path.basename(scenario_file)
    digest = hashlib.blake2b(basename.encode("utf-8"), digest_size=4).digest()
    idx = int.from_bytes(digest, "big") % len(OPERATOR_POOL_IDS)
    return OPERATOR_POOL_IDS[idx]


@dataclass(frozen=True)
class DeviceSpec:
    """One Device under the Unit: its name, pre-allocated asset_id, the
    Family it gets linked to, and that Family's pre-allocated id.

    `controller_id` is an optional back-reference to a sibling
    Device-level Asset carrying the MotionController Family that drives
    this Device. None for stages whose controller is sealed in (e.g.
    Optique Peter focus stage with PCB-integrated Nanotec stepper) or
    not yet modelled; set when the scenario opts in to the
    controller-as-Asset slice. See
    [[project-controller-as-asset-stage1-design]]. The install ceremony
    forwards this id into `register_asset` verbatim; the value flows to
    `Asset.controller_id` on the genesis event."""

    name: str
    asset_id: UUID
    cap_name: str
    cap_id: UUID
    controller_id: UUID | None = None


@dataclass(frozen=True)
class FacilityIds:
    """IDs of every aggregate registered by `install_aps_unit()`.

    Returned for callers that want to reference them post-install without
    re-importing module-level constants. Operator + reviewer + Trust-shape
    ids are fixture-owned canonical constants; the rest are scenario-
    supplied."""

    operator_pool_ids: tuple[UUID, UUID, UUID]
    beamline_scientist_actor_id: UUID
    esrb_actor_id: UUID
    unit_id: UUID
    device_ids: tuple[UUID, ...]
    cap_ids: tuple[UUID, ...]
    bm2_zone_id: UUID
    bm2_local_conduit_id: UUID
    bm2_operations_policy_id: UUID
    bm2_agent_policy_id: UUID


def facility_id_prefix(
    *,
    unit_id: UUID,
    devices: Sequence[DeviceSpec],
) -> list[UUID]:
    """FixedIdGenerator queue prefix for `install_aps_unit()`.

    Ordering mirrors the ceremony exactly:
      1. register_actor x 3 (operator pool, canonical ids): actor_id, event
      2. register_actor x 2 (BS + ESRB review-chain reviewers): actor_id, event
      3. register_asset Unit (root, facility-anchored): unit_id, event
      4. define_family x U (unique cap_names): event only (stream id derived)
      5. register_asset + add_asset_family x N: asset_id, register_event, addcap_event
      6. define_zone (2-BM Zone, canonical id): zone_id, event
      7. define_conduit (2-BM Local Conduit, self-loop): conduit_id, event
      8. define_policy x 2 (Operations + Agent, canonical ids): policy_id, event

    Family ids are derived from the name (not popped), so define_family
    consumes one event-id slot per UNIQUE cap_name, not a stream id.
    Anonymous event ids use `uuid4()`.
    """
    e = uuid4
    ids: list[UUID] = [
        # 3 operators (fixture-owned canonical UUIDs)
        OPERATOR_1_ID,
        e(),
        OPERATOR_2_ID,
        e(),
        OPERATOR_3_ID,
        e(),
        # 2 review-chain reviewers (fixture-owned canonical UUIDs)
        BEAMLINE_SCIENTIST_ACTOR_ID,
        e(),
        ESRB_ACTOR_ID,
        e(),
        # Root Asset: the beamline Unit (scenario-supplied UUID)
        unit_id,
        e(),
    ]
    seen_family_names: set[str] = set()
    for d in devices:
        if d.cap_name in seen_family_names:
            continue
        seen_family_names.add(d.cap_name)
        ids.extend([e()])
    for d in devices:
        ids.extend([d.asset_id, e(), e()])
    # Trust shape (fixture-owned canonical UUIDs).
    # define_conduit consumes FOUR slots from the id queue:
    #   1. conduit aggregate id
    #   2. verdict_logbook_id (auto-opened logbook id; see
    #      conduit/handler.py line 96 — distinct from the event id)
    #   3. ConduitDefined event id
    #   4. LogbookOpened event id
    # See conduit/state.py docstring for why the verdicts logbook
    # auto-opens at conduit-creation.
    ids.extend(
        [
            BM2_ZONE_ID,
            e(),
            BM2_LOCAL_CONDUIT_ID,
            e(),
            e(),
            e(),
            BM2_OPERATIONS_POLICY_ID,
            e(),
            BM2_AGENT_POLICY_ID,
            e(),
        ]
    )
    return ids


async def install_aps_unit(
    deps: Kernel,
    *,
    profile_store: ProfileStore,
    correlation_id: UUID,
    unit_id: UUID,
    devices: Sequence[DeviceSpec],
    unit_name: str = "2-BM",
    facility_code: str = "cora",
) -> FacilityIds:
    """Execute the canonical facility-install ceremony for a 2-BM-shape Unit.

    Order matches `facility_id_prefix()` exactly: 3 operators, BS + ESRB
    reviewers, then the beamline Unit (root), then all Capabilities
    defined, then all Devices registered + their Capabilities linked,
    then the 2-BM Trust shape (Zone + Conduit + Operations Policy +
    Agent Policy).

    All install events are attributed to `OPERATOR_1_ID` (bootstrap
    convention; the first operator-registration event is self-attributed
    by necessity, and the rest follow for narrative consistency — "the
    lead operator installed the beamline equipment").

    The beamline Unit is the ROOT Asset: it binds `facility_code`
    (default "cora", the seeded self-Facility) and carries
    `parent_id=None`. Its Devices nest under the Unit. Site / area /
    institution scope is owned by the Federation Facility aggregate,
    bound via `facility_code`, not by an Asset tier.

    `unit_name` defaults to "2-BM"; it parameterizes for future
    beamline scenarios (7-BM, 32-ID, etc.).
    """
    principal_id = OPERATOR_1_ID

    # ----- Access BC: register the 3-operator pool -----
    for actor_name in OPERATOR_NAMES:
        await bind_register_actor(deps, profile_store=profile_store)(
            RegisterActor(name=actor_name),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )

    # ----- Access BC: register review-chain reviewers (BS + ESRB) -----
    # Doc-placed at APS even though BS is beamline-named; the role the
    # BS plays in ESAF review is facility safety-process work. ESRB is
    # the facility's central safety committee, one identity facility-wide.
    await bind_register_actor(deps, profile_store=profile_store)(
        RegisterActor(name=BEAMLINE_SCIENTIST_NAME),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await bind_register_actor(deps, profile_store=profile_store)(
        RegisterActor(name=ESRB_NAME),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )

    # ----- Equipment BC: root beamline Unit (facility-anchored) + Devices -----
    await bind_register_asset(deps)(
        RegisterAsset(
            name=unit_name,
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code=facility_code,
        ),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    # Family ids are derived from the name, so two devices sharing a
    # Family (e.g. several LinearStages) must define it exactly once;
    # a second define on the same name would collide on the deterministic
    # stream. Dedup in first-appearance order.
    defined_family_names: set[str] = set()
    for d in devices:
        if d.cap_name in defined_family_names:
            continue
        defined_family_names.add(d.cap_name)
        await bind_define_family(deps)(
            DefineFamily(name=d.cap_name, affordances=frozenset()),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )
    for d in devices:
        await bind_register_asset(deps)(
            RegisterAsset(
                name=d.name,
                tier=AssetTier.DEVICE,
                parent_id=unit_id,
                controller_id=d.controller_id,
            ),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )
        await bind_add_family(deps)(
            AddAssetFamily(
                asset_id=d.asset_id,
                family_id=family_stream_id(FamilyName(d.cap_name)),
            ),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )

    # ----- Trust BC: 2-BM Zone + self-loop Conduit + 2 Policies -----
    await bind_define_zone(deps)(
        DefineZone(name=f"{unit_name} Zone"),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await bind_define_conduit(deps)(
        DefineConduit(
            name=f"{unit_name} Local Conduit",
            source_zone_id=BM2_ZONE_ID,
            target_zone_id=BM2_ZONE_ID,
        ),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await bind_define_policy(deps)(
        DefinePolicy(
            name=f"{unit_name} Operations Policy",
            conduit_id=BM2_LOCAL_CONDUIT_ID,
            permitted_principal_ids=frozenset(OPERATOR_POOL_IDS),
            permitted_commands=_OPERATIONS_COMMANDS,
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await bind_define_policy(deps)(
        DefinePolicy(
            name=f"{unit_name} Agent Policy",
            conduit_id=BM2_LOCAL_CONDUIT_ID,
            permitted_principal_ids=frozenset({RUN_DEBRIEF_ACTOR_ID}),
            permitted_commands=_AGENT_COMMANDS,
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )

    return FacilityIds(
        operator_pool_ids=OPERATOR_POOL_IDS,
        beamline_scientist_actor_id=BEAMLINE_SCIENTIST_ACTOR_ID,
        esrb_actor_id=ESRB_ACTOR_ID,
        unit_id=unit_id,
        device_ids=tuple(d.asset_id for d in devices),
        cap_ids=tuple(family_stream_id(FamilyName(d.cap_name)) for d in devices),
        bm2_zone_id=BM2_ZONE_ID,
        bm2_local_conduit_id=BM2_LOCAL_CONDUIT_ID,
        bm2_operations_policy_id=BM2_OPERATIONS_POLICY_ID,
        bm2_agent_policy_id=BM2_AGENT_POLICY_ID,
    )


__all__ = [
    "BEAMLINE_SCIENTIST_ACTOR_ID",
    "BEAMLINE_SCIENTIST_NAME",
    "BM2_AGENT_POLICY_ID",
    "BM2_LOCAL_CONDUIT_ID",
    "BM2_OPERATIONS_POLICY_ID",
    "BM2_ZONE_ID",
    "ESRB_ACTOR_ID",
    "ESRB_NAME",
    "OPERATOR_1_ID",
    "OPERATOR_2_ID",
    "OPERATOR_3_ID",
    "OPERATOR_NAMES",
    "OPERATOR_POOL_IDS",
    "RUN_DEBRIEF_ACTOR_ID",
    "DeviceSpec",
    "FacilityIds",
    "facility_id_prefix",
    "install_aps_unit",
    "operator_for",
]
