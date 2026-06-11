"""Unit tests for bind_plan_role + unbind_plan_role handlers.

Consolidated file (mirror of `test_plan_wire_slices_handlers.py`):
both role slices share the load+fold+decide+append shape, so per-slice
files would duplicate the seed-Plan/Method/Asset setup.

Coverage:
  - happy path appends the right event
  - authorize-deny -> UnauthorizedError; no event appended
  - wire_recipe exposes both handlers on the bundle
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
from cora.equipment.aggregates.family.events import (
    FamilyDefined,
)
from cora.equipment.aggregates.family.events import event_type_name as family_event_type_name
from cora.equipment.aggregates.family.events import to_payload as family_to_payload
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.recipe import UnauthorizedError, wire_recipe
from cora.recipe.aggregates.method import RoleName
from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodRequiredRoleAdded,
)
from cora.recipe.aggregates.method.events import event_type_name as method_event_type_name
from cora.recipe.aggregates.method.events import to_payload as method_to_payload
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    PlanRoleBound,
    event_type_name,
    to_payload,
)
from cora.recipe.features import bind_plan_role, unbind_plan_role
from cora.recipe.features.bind_plan_role import BindPlanRole
from cora.recipe.features.unbind_plan_role import UnbindPlanRole
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)
_PLAN_ID = UUID("01900000-0000-7000-8000-0000000ee601")
_ASSET_ID = UUID("01900000-0000-7000-8000-0000000ee602")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-0000000ee603")
_METHOD_ID = UUID("01900000-0000-7000-8000-0000000ee604")
_FAMILY_ID = UUID("01900000-0000-7000-8000-0000000ee605")
_BIND_EVENT_ID = UUID("01900000-0000-7000-8000-0000000ee606")
_UNBIND_EVENT_ID = UUID("01900000-0000-7000-8000-0000000ee607")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000ee608")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000ee609")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_BIND_EVENT_ID, _UNBIND_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _seed(store: InMemoryEventStore) -> None:
    """Seed Family + Asset + Method + Plan in the in-memory store."""
    # Family
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
    # Asset with the right family and a port covering the role's
    # required_port. The family link is a separate event
    # (AssetFamilyAdded) since AssetRegistered doesn't carry a
    # family_ids field.
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
    # Method with a required role for the bound family + port.
    method_defined = MethodDefined(
        method_id=_METHOD_ID,
        name="Tomography",
        needed_family_ids=(),
        occurred_at=_NOW,
    )
    role_added = MethodRequiredRoleAdded(
        method_id=_METHOD_ID,
        role_name="detector",
        family_id=_FAMILY_ID,
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
    # Plan binding the Asset, referencing the Method.
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


# ---------- bind_plan_role handler ----------


@pytest.mark.unit
async def test_bind_plan_role_handler_appends_event() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps(event_store=store)

    await bind_plan_role.bind(deps)(
        BindPlanRole(
            plan_id=_PLAN_ID,
            role_name=RoleName("detector"),
            asset_id=_ASSET_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Plan", _PLAN_ID)
    assert version == 2
    appended = events[1]
    assert appended.event_type == "PlanRoleBound"
    assert appended.event_id == _BIND_EVENT_ID
    assert appended.payload["role_name"] == "detector"
    assert appended.payload["asset_id"] == str(_ASSET_ID)


@pytest.mark.unit
async def test_bind_plan_role_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deny_deps = _build_deps(event_store=store, deny=True)

    with pytest.raises(UnauthorizedError):
        await bind_plan_role.bind(deny_deps)(
            BindPlanRole(
                plan_id=_PLAN_ID,
                role_name=RoleName("detector"),
                asset_id=_ASSET_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Plan", _PLAN_ID)
    assert version == 1


# ---------- unbind_plan_role handler ----------


@pytest.mark.unit
async def test_unbind_plan_role_handler_appends_event() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    # Pre-seed a binding event so unbind has something to remove.
    bound = PlanRoleBound(
        plan_id=_PLAN_ID,
        role_name="detector",
        asset_id=_ASSET_ID,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Plan",
        stream_id=_PLAN_ID,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(bound),
                payload=to_payload(bound),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="Seed",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
        ],
    )
    deps = _build_deps(event_store=store)
    await unbind_plan_role.bind(deps)(
        UnbindPlanRole(plan_id=_PLAN_ID, role_name=RoleName("detector")),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Plan", _PLAN_ID)
    assert version == 3
    appended = events[2]
    assert appended.event_type == "PlanRoleUnbound"
    assert appended.payload["role_name"] == "detector"


@pytest.mark.unit
async def test_handlers_wired_into_recipe_handlers_bundle() -> None:
    deps = _build_deps()
    handlers = wire_recipe(deps)
    assert handlers.bind_plan_role is not None
    assert callable(handlers.bind_plan_role)
    assert handlers.unbind_plan_role is not None
    assert callable(handlers.unbind_plan_role)
