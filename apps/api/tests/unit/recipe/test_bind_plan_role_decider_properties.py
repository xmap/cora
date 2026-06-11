"""Property-based tests for `bind_plan_role.decide` (Recipe BC, slice 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetName,
    AssetPort,
    PortDirection,
)
from cora.recipe.aggregates.method import (
    Method,
    MethodName,
    PortRequirement,
    RoleName,
    RoleRequirement,
)
from cora.recipe.aggregates.plan import (
    Plan,
    PlanCannotMutateRoleBindingsError,
    PlanName,
    PlanNotFoundError,
    PlanRoleAlreadyBoundError,
    PlanRoleAssetNotBoundError,
    PlanRoleBound,
    PlanRoleNameNotDeclaredError,
    PlanStatus,
    RoleBinding,
)
from cora.recipe.features import bind_plan_role
from cora.recipe.features.bind_plan_role import BindPlanRole, BindPlanRoleContext

if TYPE_CHECKING:
    from datetime import datetime

_VALID_ROLE_NAME = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=50,
)
_NON_DEFINED_STATUS = st.sampled_from([PlanStatus.VERSIONED, PlanStatus.DEPRECATED])
_ANY_DATETIME = st.datetimes()


def _plan(
    *,
    asset_ids: frozenset[UUID] | None = None,
    status: PlanStatus = PlanStatus.DEFINED,
    role_bindings: frozenset[RoleBinding] | None = None,
) -> Plan:
    aid = uuid4()
    return Plan(
        id=uuid4(),
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=asset_ids if asset_ids is not None else frozenset({aid}),
        status=status,
        method_id=uuid4(),
        role_bindings=role_bindings if role_bindings is not None else frozenset(),
    )


def _asset_with(family_id: UUID, port: PortRequirement | None = None) -> Asset:
    from cora.equipment.aggregates.asset import AssetTier

    ports: frozenset[AssetPort] = frozenset()
    if port is not None:
        ports = frozenset[AssetPort](
            {AssetPort(name=port.port_name, direction=port.direction, signal_type=port.signal_type)}
        )
    return Asset(
        id=uuid4(),
        name=AssetName("a"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=frozenset({family_id}),
        ports=ports,
    )


_NOOP_CONTEXT = BindPlanRoleContext(method=None, asset=None)


@pytest.mark.unit
@given(role_name=_VALID_ROLE_NAME, now=_ANY_DATETIME)
def test_state_none_always_raises_plan_not_found(role_name: str, now: datetime) -> None:
    assume(role_name == role_name.strip())
    with pytest.raises(PlanNotFoundError):
        bind_plan_role.decide(
            state=None,
            command=BindPlanRole(
                plan_id=uuid4(),
                role_name=RoleName(role_name),
                asset_id=uuid4(),
            ),
            context=_NOOP_CONTEXT,
            now=now,
        )


@pytest.mark.unit
@given(
    role_name=_VALID_ROLE_NAME,
    status=_NON_DEFINED_STATUS,
    now=_ANY_DATETIME,
)
def test_non_defined_status_always_raises_cannot_mutate(
    role_name: str, status: PlanStatus, now: datetime
) -> None:
    assume(role_name == role_name.strip())
    state = _plan(status=status)
    with pytest.raises(PlanCannotMutateRoleBindingsError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName(role_name),
                asset_id=next(iter(state.asset_ids)),
            ),
            context=_NOOP_CONTEXT,
            now=now,
        )


@pytest.mark.unit
@given(role_name=_VALID_ROLE_NAME, now=_ANY_DATETIME)
def test_asset_not_bound_always_raises_asset_not_bound(role_name: str, now: datetime) -> None:
    assume(role_name == role_name.strip())
    state = _plan()
    unbound_asset_id = uuid4()
    with pytest.raises(PlanRoleAssetNotBoundError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName(role_name),
                asset_id=unbound_asset_id,
            ),
            context=_NOOP_CONTEXT,
            now=now,
        )


@pytest.mark.unit
@given(role_name=_VALID_ROLE_NAME, now=_ANY_DATETIME)
def test_duplicate_role_name_always_raises_already_bound(role_name: str, now: datetime) -> None:
    assume(role_name == role_name.strip())
    aid = uuid4()
    state = _plan(
        asset_ids=frozenset({aid}),
        role_bindings=frozenset({RoleBinding(role_name=RoleName(role_name), asset_id=aid)}),
    )
    # Asset exists; method has the role; family + ports cover. The
    # duplicate role_name guard fires before any of those.
    from cora.equipment.aggregates.asset import AssetTier

    asset = Asset(
        id=aid,
        name=AssetName("a"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=frozenset(),
        ports=frozenset(),
    )
    method = Method(
        id=uuid4(),
        name=MethodName("m"),
        required_roles=frozenset(),
    )
    with pytest.raises(PlanRoleAlreadyBoundError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName(role_name),
                asset_id=aid,
            ),
            context=BindPlanRoleContext(method=method, asset=asset),
            now=now,
        )


@pytest.mark.unit
@given(role_name=_VALID_ROLE_NAME, now=_ANY_DATETIME)
def test_happy_path_emits_single_event_with_injected_fields(role_name: str, now: datetime) -> None:
    assume(role_name == role_name.strip())
    aid = uuid4()
    fid = uuid4()
    state = _plan(asset_ids=frozenset({aid}))
    method = Method(
        id=uuid4(),
        name=MethodName("m"),
        required_roles=frozenset({RoleRequirement(role_name=RoleName(role_name), family_id=fid)}),
    )
    from cora.equipment.aggregates.asset import AssetTier

    asset = Asset(
        id=aid,
        name=AssetName("a"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=frozenset({fid}),
        ports=frozenset(),
    )
    events = bind_plan_role.decide(
        state=state,
        command=BindPlanRole(
            plan_id=state.id,
            role_name=RoleName(role_name),
            asset_id=aid,
        ),
        context=BindPlanRoleContext(method=method, asset=asset),
        now=now,
    )
    assert events == [
        PlanRoleBound(
            plan_id=state.id,
            role_name=role_name,
            asset_id=aid,
            occurred_at=now,
        )
    ]


# Suppress unused-import lint for imports kept for future PBT
# expansions (currently unused by the property bodies above).
_: tuple[object, ...] = (
    PortDirection,
    PortRequirement,
    PlanRoleNameNotDeclaredError,
    _asset_with,
)
