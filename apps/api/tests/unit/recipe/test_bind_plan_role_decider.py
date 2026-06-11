"""Unit tests for the `bind_plan_role` slice's pure decider.

The decider validates against Plan + Method + Asset state (cross-
aggregate). Helpers construct minimal Plan/Method/Asset fixtures
in-memory; the handler's role of loading streams is bypassed here
by passing the context directly.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetName,
    AssetNotFoundError,
    AssetPort,
    PortDirection,
)
from cora.recipe.aggregates.method import (
    Method,
    MethodName,
    MethodNotFoundError,
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
    PlanRoleFamilyMismatchError,
    PlanRoleNameNotDeclaredError,
    PlanRolePortCoverageNotSatisfiedError,
    PlanStatus,
    PlanWireRoleEndpointMismatchError,
    RoleBinding,
    Wire,
)
from cora.recipe.features import bind_plan_role
from cora.recipe.features.bind_plan_role import BindPlanRole, BindPlanRoleContext

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)


def _plan(
    *,
    asset_ids: frozenset[UUID] | None = None,
    method_id: UUID | None = None,
    status: PlanStatus = PlanStatus.DEFINED,
    role_bindings: frozenset[RoleBinding] | None = None,
    wires: frozenset[Wire] | None = None,
) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=asset_ids if asset_ids is not None else frozenset({uuid4()}),
        status=status,
        method_id=method_id or uuid4(),
        role_bindings=role_bindings if role_bindings is not None else frozenset(),
        wires=wires if wires is not None else frozenset(),
    )


def _method(*, required_roles: frozenset[RoleRequirement] | None = None) -> Method:
    return Method(
        id=uuid4(),
        name=MethodName("m"),
        required_roles=required_roles if required_roles is not None else frozenset(),
    )


def _asset(
    *,
    family_ids: frozenset[UUID] | None = None,
    ports: frozenset[AssetPort] | None = None,
) -> Asset:
    from cora.equipment.aggregates.asset import AssetTier

    return Asset(
        id=uuid4(),
        name=AssetName("a"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=family_ids if family_ids is not None else frozenset(),
        ports=ports if ports is not None else frozenset(),
    )


def _cmd(plan: Plan, asset: Asset, role_name: str = "detector") -> BindPlanRole:
    return BindPlanRole(
        plan_id=plan.id,
        role_name=RoleName(role_name),
        asset_id=asset.id,
    )


_NOOP_CONTEXT = BindPlanRoleContext(method=None, asset=None)


@pytest.mark.unit
def test_state_none_raises_plan_not_found() -> None:
    with pytest.raises(PlanNotFoundError):
        bind_plan_role.decide(
            state=None,
            command=BindPlanRole(
                plan_id=uuid4(),
                role_name=RoleName("detector"),
                asset_id=uuid4(),
            ),
            context=_NOOP_CONTEXT,
            now=_NOW,
        )


@pytest.mark.unit
def test_status_versioned_raises_cannot_mutate() -> None:
    state = _plan(status=PlanStatus.VERSIONED)
    asset = _asset()
    with pytest.raises(PlanCannotMutateRoleBindingsError) as exc:
        bind_plan_role.decide(
            state=state,
            command=_cmd(state, asset),
            context=_NOOP_CONTEXT,
            now=_NOW,
        )
    assert exc.value.current_status is PlanStatus.VERSIONED


@pytest.mark.unit
def test_asset_not_in_plan_asset_ids_raises_asset_not_bound() -> None:
    state = _plan(asset_ids=frozenset({uuid4()}))
    asset = _asset()  # asset.id is fresh, not in state.asset_ids
    with pytest.raises(PlanRoleAssetNotBoundError):
        bind_plan_role.decide(
            state=state,
            command=_cmd(state, asset),
            context=_NOOP_CONTEXT,
            now=_NOW,
        )


@pytest.mark.unit
def test_duplicate_role_name_raises_already_bound() -> None:
    aid = uuid4()
    state = _plan(
        asset_ids=frozenset({aid}),
        role_bindings=frozenset(
            {RoleBinding(role_name=RoleName("detector"), asset_id=aid)},
        ),
    )
    # asset.id == aid -> in asset_ids -> passes asset check
    asset = Asset(
        id=aid,
        name=AssetName("a"),
        tier=__import__("cora.equipment.aggregates.asset", fromlist=["AssetTier"]).AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=frozenset(),
        ports=frozenset(),
    )
    with pytest.raises(PlanRoleAlreadyBoundError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),
                asset_id=aid,
            ),
            context=BindPlanRoleContext(method=_method(), asset=asset),
            now=_NOW,
        )


@pytest.mark.unit
def test_method_missing_raises_method_not_found() -> None:
    aid = uuid4()
    state = _plan(asset_ids=frozenset({aid}))
    with pytest.raises(MethodNotFoundError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),
                asset_id=aid,
            ),
            context=BindPlanRoleContext(method=None, asset=_asset()),
            now=_NOW,
        )


@pytest.mark.unit
def test_role_name_not_declared_on_method_raises_not_declared() -> None:
    aid = uuid4()
    state = _plan(asset_ids=frozenset({aid}))
    method = _method(
        required_roles=frozenset(
            {
                RoleRequirement(role_name=RoleName("sample_monitor"), family_id=uuid4()),
            }
        )
    )
    asset = Asset(
        id=aid,
        name=AssetName("a"),
        tier=__import__("cora.equipment.aggregates.asset", fromlist=["AssetTier"]).AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=frozenset(),
        ports=frozenset(),
    )
    with pytest.raises(PlanRoleNameNotDeclaredError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),  # not in method.required_roles
                asset_id=aid,
            ),
            context=BindPlanRoleContext(method=method, asset=asset),
            now=_NOW,
        )


@pytest.mark.unit
def test_asset_missing_raises_asset_not_found() -> None:
    aid = uuid4()
    state = _plan(asset_ids=frozenset({aid}))
    method = _method(
        required_roles=frozenset(
            {RoleRequirement(role_name=RoleName("detector"), family_id=uuid4())}
        )
    )
    with pytest.raises(AssetNotFoundError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),
                asset_id=aid,
            ),
            context=BindPlanRoleContext(method=method, asset=None),
            now=_NOW,
        )


@pytest.mark.unit
def test_family_mismatch_raises_family_mismatch() -> None:
    aid = uuid4()
    required_family_id = uuid4()
    state = _plan(asset_ids=frozenset({aid}))
    method = _method(
        required_roles=frozenset(
            {
                RoleRequirement(
                    role_name=RoleName("detector"),
                    family_id=required_family_id,
                ),
            }
        )
    )
    asset = Asset(
        id=aid,
        name=AssetName("a"),
        tier=__import__("cora.equipment.aggregates.asset", fromlist=["AssetTier"]).AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=frozenset({uuid4()}),  # different family
        ports=frozenset(),
    )
    with pytest.raises(PlanRoleFamilyMismatchError) as exc:
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),
                asset_id=aid,
            ),
            context=BindPlanRoleContext(method=method, asset=asset),
            now=_NOW,
        )
    assert exc.value.required_family_id == required_family_id


@pytest.mark.unit
def test_port_coverage_missing_raises_port_coverage_not_satisfied() -> None:
    aid = uuid4()
    fid = uuid4()
    state = _plan(asset_ids=frozenset({aid}))
    method = _method(
        required_roles=frozenset(
            {
                RoleRequirement(
                    role_name=RoleName("detector"),
                    family_id=fid,
                    required_ports=frozenset(
                        {
                            PortRequirement(
                                port_name="trigger_in",
                                direction=PortDirection.INPUT,
                                signal_type="TTL",
                            ),
                        }
                    ),
                ),
            }
        )
    )
    # Asset has the right family but a DIFFERENT port (mismatched signal_type)
    asset = Asset(
        id=aid,
        name=AssetName("a"),
        tier=__import__("cora.equipment.aggregates.asset", fromlist=["AssetTier"]).AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=frozenset({fid}),
        ports=frozenset(
            {
                AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="LVDS"),
            }
        ),
    )
    with pytest.raises(PlanRolePortCoverageNotSatisfiedError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),
                asset_id=aid,
            ),
            context=BindPlanRoleContext(method=method, asset=asset),
            now=_NOW,
        )


@pytest.mark.unit
def test_happy_path_emits_plan_role_bound_event() -> None:
    aid = uuid4()
    fid = uuid4()
    state = _plan(asset_ids=frozenset({aid}))
    method = _method(
        required_roles=frozenset(
            {
                RoleRequirement(
                    role_name=RoleName("detector"),
                    family_id=fid,
                    required_ports=frozenset(
                        {
                            PortRequirement(
                                port_name="trigger_in",
                                direction=PortDirection.INPUT,
                                signal_type="TTL",
                            ),
                        }
                    ),
                ),
            }
        )
    )
    asset = Asset(
        id=aid,
        name=AssetName("a"),
        tier=__import__("cora.equipment.aggregates.asset", fromlist=["AssetTier"]).AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=frozenset({fid}),
        ports=frozenset(
            {AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")}
        ),
    )
    events = bind_plan_role.decide(
        state=state,
        command=BindPlanRole(
            plan_id=state.id,
            role_name=RoleName("detector"),
            asset_id=aid,
        ),
        context=BindPlanRoleContext(method=method, asset=asset),
        now=_NOW,
    )
    assert events == [
        PlanRoleBound(
            plan_id=state.id,
            role_name="detector",
            asset_id=aid,
            occurred_at=_NOW,
        )
    ]


def _device_asset(
    *,
    asset_id: UUID,
    family_ids: frozenset[UUID],
    ports: frozenset[AssetPort],
) -> Asset:
    from cora.equipment.aggregates.asset import AssetTier

    return Asset(
        id=asset_id,
        name=AssetName("a"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=family_ids,
        ports=ports,
    )


def _output_wire(
    *,
    source_asset_id: UUID,
    source_port: str = "data_out",
    target_asset_id: UUID | None = None,
    target_port: str = "data_in",
) -> Wire:
    return Wire(
        source_asset_id=source_asset_id,
        source_port_name=source_port,
        target_asset_id=target_asset_id if target_asset_id is not None else uuid4(),
        target_port_name=target_port,
    )


def _input_wire(
    *,
    target_asset_id: UUID,
    target_port: str = "trigger_in",
    source_asset_id: UUID | None = None,
    source_port: str = "trigger_out",
) -> Wire:
    return Wire(
        source_asset_id=source_asset_id if source_asset_id is not None else uuid4(),
        source_port_name=source_port,
        target_asset_id=target_asset_id,
        target_port_name=target_port,
    )


@pytest.mark.unit
def test_wire_then_bind_existing_output_wire_at_wrong_asset_raises_role_endpoint_mismatch() -> None:
    """An OUTPUT wire installed before binding fixes the source-side Asset.

    If the operator wires `data_out` first and then tries to bind the
    detector role to a DIFFERENT Asset, the wire graph and the role
    table would silently diverge. The bind decider must reject.
    """
    candidate_aid = uuid4()
    wire_aid = uuid4()
    fid = uuid4()
    state = _plan(
        asset_ids=frozenset({candidate_aid, wire_aid}),
        wires=frozenset({_output_wire(source_asset_id=wire_aid, source_port="data_out")}),
    )
    method = _method(
        required_roles=frozenset(
            {
                RoleRequirement(
                    role_name=RoleName("detector"),
                    family_id=fid,
                    required_ports=frozenset(
                        {
                            PortRequirement(
                                port_name="data_out",
                                direction=PortDirection.OUTPUT,
                                signal_type="frame",
                            ),
                        }
                    ),
                ),
            }
        )
    )
    asset = _device_asset(
        asset_id=candidate_aid,
        family_ids=frozenset({fid}),
        ports=frozenset(
            {AssetPort(name="data_out", direction=PortDirection.OUTPUT, signal_type="frame")}
        ),
    )
    with pytest.raises(PlanWireRoleEndpointMismatchError) as exc:
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),
                asset_id=candidate_aid,
            ),
            context=BindPlanRoleContext(method=method, asset=asset),
            now=_NOW,
        )
    assert exc.value.endpoint_role == "source"
    assert exc.value.expected_asset_id == candidate_aid
    assert exc.value.actual_asset_id == wire_aid


@pytest.mark.unit
def test_wire_then_bind_existing_input_wire_at_wrong_asset_raises_role_endpoint_mismatch() -> None:
    """An INPUT wire installed before binding fixes the target-side Asset.

    Symmetric to the OUTPUT case: if the role's required_port has
    direction INPUT, an existing wire whose `target_port_name` matches
    at a different Asset rejects the bind.
    """
    candidate_aid = uuid4()
    wire_aid = uuid4()
    fid = uuid4()
    state = _plan(
        asset_ids=frozenset({candidate_aid, wire_aid}),
        wires=frozenset({_input_wire(target_asset_id=wire_aid, target_port="trigger_in")}),
    )
    method = _method(
        required_roles=frozenset(
            {
                RoleRequirement(
                    role_name=RoleName("detector"),
                    family_id=fid,
                    required_ports=frozenset(
                        {
                            PortRequirement(
                                port_name="trigger_in",
                                direction=PortDirection.INPUT,
                                signal_type="TTL",
                            ),
                        }
                    ),
                ),
            }
        )
    )
    asset = _device_asset(
        asset_id=candidate_aid,
        family_ids=frozenset({fid}),
        ports=frozenset(
            {AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")}
        ),
    )
    with pytest.raises(PlanWireRoleEndpointMismatchError) as exc:
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),
                asset_id=candidate_aid,
            ),
            context=BindPlanRoleContext(method=method, asset=asset),
            now=_NOW,
        )
    assert exc.value.endpoint_role == "target"
    assert exc.value.expected_asset_id == candidate_aid
    assert exc.value.actual_asset_id == wire_aid


@pytest.mark.unit
def test_unbind_rebind_to_different_asset_raises_role_endpoint_mismatch() -> None:
    """Wires survive an unbind, so rebinding the role to a different Asset diverges.

    The unbind_plan_role slice does NOT cascade-delete wires that
    reference the unbound role's port. If the operator then rebinds
    to a different Asset, the bind decider must catch the divergence.
    """
    original_aid = uuid4()
    new_aid = uuid4()
    fid = uuid4()
    # Plan state AFTER unbind: role_bindings is empty, wires still
    # reference the original_aid on `data_out`.
    state = _plan(
        asset_ids=frozenset({original_aid, new_aid}),
        role_bindings=frozenset(),
        wires=frozenset({_output_wire(source_asset_id=original_aid, source_port="data_out")}),
    )
    method = _method(
        required_roles=frozenset(
            {
                RoleRequirement(
                    role_name=RoleName("detector"),
                    family_id=fid,
                    required_ports=frozenset(
                        {
                            PortRequirement(
                                port_name="data_out",
                                direction=PortDirection.OUTPUT,
                                signal_type="frame",
                            ),
                        }
                    ),
                ),
            }
        )
    )
    new_asset = _device_asset(
        asset_id=new_aid,
        family_ids=frozenset({fid}),
        ports=frozenset(
            {AssetPort(name="data_out", direction=PortDirection.OUTPUT, signal_type="frame")}
        ),
    )
    with pytest.raises(PlanWireRoleEndpointMismatchError) as exc:
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),
                asset_id=new_aid,
            ),
            context=BindPlanRoleContext(method=method, asset=new_asset),
            now=_NOW,
        )
    assert exc.value.endpoint_role == "source"
    assert exc.value.actual_asset_id == original_aid


@pytest.mark.unit
def test_wire_at_correct_asset_passes_bind_role_endpoint_check() -> None:
    """A pre-installed wire whose endpoint matches the candidate Asset is fine.

    The role-endpoint check only fires when the wire endpoint is at a
    DIFFERENT Asset; same-Asset wires are the supported bind-after-wire
    ordering that the slice should not block.
    """
    candidate_aid = uuid4()
    fid = uuid4()
    state = _plan(
        asset_ids=frozenset({candidate_aid, uuid4()}),
        wires=frozenset({_output_wire(source_asset_id=candidate_aid, source_port="data_out")}),
    )
    method = _method(
        required_roles=frozenset(
            {
                RoleRequirement(
                    role_name=RoleName("detector"),
                    family_id=fid,
                    required_ports=frozenset(
                        {
                            PortRequirement(
                                port_name="data_out",
                                direction=PortDirection.OUTPUT,
                                signal_type="frame",
                            ),
                        }
                    ),
                ),
            }
        )
    )
    asset = _device_asset(
        asset_id=candidate_aid,
        family_ids=frozenset({fid}),
        ports=frozenset(
            {AssetPort(name="data_out", direction=PortDirection.OUTPUT, signal_type="frame")}
        ),
    )
    events = bind_plan_role.decide(
        state=state,
        command=BindPlanRole(
            plan_id=state.id,
            role_name=RoleName("detector"),
            asset_id=candidate_aid,
        ),
        context=BindPlanRoleContext(method=method, asset=asset),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], PlanRoleBound)


# unused warning suppression
_ = Any
