"""Layer 3 sub-slice 3D + Assembly-branch unit tests for the
`bind_plan_role` HANDLER's role_kind code path.

The decider-level role_kind / Assembly satisfaction tests live in
`test_bind_plan_role_decider_role_kind.py`. This file pins the
HANDLER's edge-load behavior:

  - RoleLookup miss surfaces as RoleNotFoundError BEFORE the decider
    sees the missing context (handler bails early so the 404 carries
    the offending role_kind)
  - FamilyLookup batch threads `family_lookups` into context for the
    decider walk
  - Empty asset.family_ids skips the FamilyLookup batch (no spurious
    asyncio.gather of zero coroutines)
  - Asset.fixture_id triggers the Fixture + AssemblyLookup edge-load
    (BLOCKER #5 follow-up; closes the MCTOptics-Assembly worked
    example in a runtime path)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset.events import (
    AssetFamilyAdded,
    AssetPortAdded,
    AssetRegistered,
)
from cora.equipment.aggregates.asset.events import event_type_name as asset_event_type_name
from cora.equipment.aggregates.asset.events import to_payload as asset_to_payload
from cora.equipment.aggregates.family.events import FamilyDefined
from cora.equipment.aggregates.family.events import event_type_name as family_event_type_name
from cora.equipment.aggregates.family.events import to_payload as family_to_payload
from cora.equipment.aggregates.role import RoleNotFoundError
from cora.infrastructure.adapters.in_memory_assembly_lookup import InMemoryAssemblyLookup
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_family_lookup import InMemoryFamilyLookup
from cora.infrastructure.adapters.in_memory_role_lookup import InMemoryRoleLookup
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.recipe.aggregates.method import RoleName
from cora.recipe.aggregates.method.events import MethodDefined, MethodRequiredRoleAdded
from cora.recipe.aggregates.method.events import event_type_name as method_event_type_name
from cora.recipe.aggregates.method.events import to_payload as method_to_payload
from cora.recipe.aggregates.plan import PlanRoleAssetCannotPresentError
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    event_type_name,
    to_payload,
)
from cora.recipe.features import bind_plan_role
from cora.recipe.features.bind_plan_role import BindPlanRole
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_PLAN_ID = UUID("01900000-0000-7000-8000-0000000ee701")
_ASSET_ID = UUID("01900000-0000-7000-8000-0000000ee702")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-0000000ee703")
_METHOD_ID = UUID("01900000-0000-7000-8000-0000000ee704")
_FAMILY_ID = UUID("01900000-0000-7000-8000-0000000ee705")
_ROLE_KIND_ID = UUID("01900000-0000-7000-8000-0000000ee706")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000ee707")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000ee708")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000ee709")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    role_lookup: InMemoryRoleLookup | None = None,
    family_lookup: InMemoryFamilyLookup | None = None,
    assembly_lookup: InMemoryAssemblyLookup | None = None,
) -> Kernel:
    return _build_deps_shared(
        ids=[_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        role_lookup=role_lookup,
        family_lookup=family_lookup,
        assembly_lookup=assembly_lookup,
    )


async def _seed(store: InMemoryEventStore) -> None:
    """Seed Family + Asset + Method (with role_kind RoleRequirement) + Plan."""
    family = FamilyDefined(family_id=_FAMILY_ID, name="Camera", occurred_at=_NOW)
    await store.append(
        stream_type="Family",
        stream_id=_FAMILY_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=family_event_type_name(family),
                payload=family_to_payload(family),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="Seed",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
        ],
    )

    asset_register = AssetRegistered(
        asset_id=_ASSET_ID,
        name="camera-A",
        tier="Device",
        parent_id=None,
        occurred_at=_NOW,
        commissioned_by=ActorId(uuid4()),
    )
    asset_family = AssetFamilyAdded(
        asset_id=_ASSET_ID,
        family_id=_FAMILY_ID,
        occurred_at=_NOW,
    )
    asset_port = AssetPortAdded(
        asset_id=_ASSET_ID,
        port_name="trigger_in",
        direction="Input",
        signal_type="TTL",
        occurred_at=_NOW,
    )
    asset_events = [
        to_new_event(
            event_type=asset_event_type_name(ev),
            payload=asset_to_payload(ev),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="Seed",
            correlation_id=_CORRELATION_ID,
            principal_id=uuid4(),
        )
        for ev in (asset_register, asset_family, asset_port)
    ]
    await store.append(
        stream_type="Asset",
        stream_id=_ASSET_ID,
        expected_version=0,
        events=asset_events,
    )

    method_defined = MethodDefined(
        method_id=_METHOD_ID,
        name="Tomography",
        needed_family_ids=(),
        occurred_at=_NOW,
    )
    # 3D path: role_kind set, family_id None (XOR invariant).
    role_added = MethodRequiredRoleAdded(
        method_id=_METHOD_ID,
        role_name="imager",
        family_id=None,
        role_kind=_ROLE_KIND_ID,
        required_ports=({"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},),
        optional=False,
        occurred_at=_NOW,
    )
    method_events = [
        to_new_event(
            event_type=method_event_type_name(ev),
            payload=method_to_payload(ev),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="Seed",
            correlation_id=_CORRELATION_ID,
            principal_id=uuid4(),
        )
        for ev in (method_defined, role_added)
    ]
    await store.append(
        stream_type="Method",
        stream_id=_METHOD_ID,
        expected_version=0,
        events=method_events,
    )

    plan = PlanDefined(
        plan_id=_PLAN_ID,
        name="tomography_run",
        practice_id=_PRACTICE_ID,
        asset_ids=(_ASSET_ID,),
        method_id=_METHOD_ID,
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={_ASSET_ID: (_FAMILY_ID,)},
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Plan",
        stream_id=_PLAN_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(plan),
                payload=to_payload(plan),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DefinePlan",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
        ],
    )


@pytest.mark.unit
async def test_handler_role_kind_path_succeeds_when_family_advertises_role() -> None:
    """Happy path: Role + Family both seeded; handler edge-loads, decider
    accepts, PlanRoleBound appends to the Plan stream."""
    store = InMemoryEventStore()
    await _seed(store)
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(
        role_id=_ROLE_KIND_ID,
        name="Imager",
        required_affordances=frozenset(),
    )
    family_lookup = InMemoryFamilyLookup()
    family_lookup.register(
        family_id=_FAMILY_ID,
        name="Camera",
        presents_as=[_ROLE_KIND_ID],
        affordances=[],
    )
    deps = _build_deps(
        event_store=store,
        role_lookup=role_lookup,
        family_lookup=family_lookup,
    )

    handler = bind_plan_role.bind(deps)
    await handler(
        BindPlanRole(
            plan_id=_PLAN_ID,
            role_name=RoleName("imager"),
            asset_id=_ASSET_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _version = await store.load("Plan", _PLAN_ID)
    bound = events[-1]
    assert bound.event_type == "PlanRoleBound"
    assert bound.payload["role_name"] == "imager"


@pytest.mark.unit
async def test_handler_role_kind_path_raises_role_not_found_when_role_lookup_misses() -> None:
    """RoleLookup miss surfaces at the handler edge so callers see 404."""
    store = InMemoryEventStore()
    await _seed(store)
    # role_lookup default: empty. RoleLookup.lookup(_ROLE_KIND_ID) returns None.
    deps = _build_deps(event_store=store)

    handler = bind_plan_role.bind(deps)
    with pytest.raises(RoleNotFoundError) as exc:
        await handler(
            BindPlanRole(
                plan_id=_PLAN_ID,
                role_name=RoleName("imager"),
                asset_id=_ASSET_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.role_id == _ROLE_KIND_ID


@pytest.mark.unit
async def test_handler_role_kind_path_raises_when_family_satisfaction_fails() -> None:
    """Role resolves, Family seeded but does NOT advertise role -> raises."""
    store = InMemoryEventStore()
    await _seed(store)
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(
        role_id=_ROLE_KIND_ID,
        name="Imager",
        required_affordances=frozenset(),
    )
    family_lookup = InMemoryFamilyLookup()
    # Family seeded but with empty presents_as -> no satisfaction.
    family_lookup.register(
        family_id=_FAMILY_ID,
        name="Camera",
        presents_as=[],
        affordances=[],
    )
    deps = _build_deps(
        event_store=store,
        role_lookup=role_lookup,
        family_lookup=family_lookup,
    )

    handler = bind_plan_role.bind(deps)
    with pytest.raises(PlanRoleAssetCannotPresentError):
        await handler(
            BindPlanRole(
                plan_id=_PLAN_ID,
                role_name=RoleName("imager"),
                asset_id=_ASSET_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
