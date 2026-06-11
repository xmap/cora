"""Unit tests for the slice-2 role-endpoint check in `add_plan_wire`.

The check is the structural closure that prevents the role-table and
the wire-graph from diverging silently. Fires when a candidate Wire's
endpoint port matches a `RoleRequirement.required_ports` entry but
the wire's endpoint Asset is not the one bound to that role.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

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
    PlanName,
    PlanStatus,
    PlanWireRoleEndpointMismatchError,
    RoleBinding,
)
from cora.recipe.features import add_plan_wire
from cora.recipe.features.add_plan_wire import AddPlanWire
from cora.recipe.features.add_plan_wire.context import PlanWireContext

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)


def _asset(
    asset_id: UUID,
    *,
    ports: frozenset[AssetPort] | None = None,
) -> Asset:
    from cora.equipment.aggregates.asset import AssetTier

    return Asset(
        id=asset_id,
        name=AssetName("a"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=frozenset(),
        ports=ports if ports is not None else frozenset(),
    )


def _plan_with(
    *,
    asset_ids: frozenset[UUID],
    role_bindings: frozenset[RoleBinding],
    method_id: UUID,
) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=asset_ids,
        status=PlanStatus.DEFINED,
        method_id=method_id,
        role_bindings=role_bindings,
    )


def _method_with_detector_image_out(method_id: UUID, fid: UUID) -> Method:
    return Method(
        id=method_id,
        name=MethodName("m"),
        required_roles=frozenset(
            {
                RoleRequirement(
                    role_name=RoleName("detector"),
                    family_id=fid,
                    required_ports=frozenset(
                        {
                            PortRequirement(
                                port_name="image_out",
                                direction=PortDirection.OUTPUT,
                                signal_type="Network",
                            ),
                        }
                    ),
                ),
            }
        ),
    )


@pytest.mark.unit
def test_wire_source_port_matches_role_required_port_but_wrong_asset_raises() -> None:
    """The bug scenario: role DETECTOR bound to camera_A, but operator
    tries to add wire (camera_B, image_out) -> (sink, in). camera_B
    has its own image_out port too; the role check rejects."""
    cam_a = uuid4()
    cam_b = uuid4()
    sink = uuid4()
    fid = uuid4()
    method_id = uuid4()
    method = _method_with_detector_image_out(method_id, fid)
    state = _plan_with(
        asset_ids=frozenset({cam_a, cam_b, sink}),
        role_bindings=frozenset(
            {RoleBinding(role_name=RoleName("detector"), asset_id=cam_a)},
        ),
        method_id=method_id,
    )
    # Both cameras carry the same port name.
    image_out = AssetPort(name="image_out", direction=PortDirection.OUTPUT, signal_type="Network")
    sink_in = AssetPort(name="in", direction=PortDirection.INPUT, signal_type="Network")
    assets = {
        cam_a: _asset(cam_a, ports=frozenset({image_out})),
        cam_b: _asset(cam_b, ports=frozenset({image_out})),
        sink: _asset(sink, ports=frozenset({sink_in})),
    }
    context = PlanWireContext(assets=assets, method=method)

    with pytest.raises(PlanWireRoleEndpointMismatchError) as exc:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=cam_b,
                source_port_name="image_out",
                target_asset_id=sink,
                target_port_name="in",
            ),
            context=context,
            now=_NOW,
        )
    assert exc.value.endpoint_role == "source"
    assert exc.value.expected_asset_id == cam_a
    assert exc.value.actual_asset_id == cam_b


@pytest.mark.unit
def test_wire_source_port_matches_role_required_port_at_correct_asset_passes() -> None:
    """Same role binding, but wire correctly terminates at camera_A.
    Should pass the role check (and the rest of the validation)."""
    cam_a = uuid4()
    sink = uuid4()
    fid = uuid4()
    method_id = uuid4()
    method = _method_with_detector_image_out(method_id, fid)
    state = _plan_with(
        asset_ids=frozenset({cam_a, sink}),
        role_bindings=frozenset(
            {RoleBinding(role_name=RoleName("detector"), asset_id=cam_a)},
        ),
        method_id=method_id,
    )
    image_out = AssetPort(name="image_out", direction=PortDirection.OUTPUT, signal_type="Network")
    sink_in = AssetPort(name="in", direction=PortDirection.INPUT, signal_type="Network")
    assets = {
        cam_a: _asset(cam_a, ports=frozenset({image_out})),
        sink: _asset(sink, ports=frozenset({sink_in})),
    }
    context = PlanWireContext(assets=assets, method=method)

    events = add_plan_wire.decide(
        state=state,
        command=AddPlanWire(
            plan_id=state.id,
            source_asset_id=cam_a,
            source_port_name="image_out",
            target_asset_id=sink,
            target_port_name="in",
        ),
        context=context,
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_wire_with_unrelated_port_name_passes_even_when_role_bound() -> None:
    """A wire using a port name that no role's required_ports claims
    is not subject to the role check."""
    cam_a = uuid4()
    sink = uuid4()
    fid = uuid4()
    method_id = uuid4()
    method = _method_with_detector_image_out(method_id, fid)
    state = _plan_with(
        asset_ids=frozenset({cam_a, sink}),
        role_bindings=frozenset(
            {RoleBinding(role_name=RoleName("detector"), asset_id=cam_a)},
        ),
        method_id=method_id,
    )
    settings_out = AssetPort(
        name="settings_out", direction=PortDirection.OUTPUT, signal_type="JSON"
    )
    sink_in = AssetPort(name="in", direction=PortDirection.INPUT, signal_type="JSON")
    assets = {
        cam_a: _asset(cam_a, ports=frozenset({settings_out})),
        sink: _asset(sink, ports=frozenset({sink_in})),
    }
    context = PlanWireContext(assets=assets, method=method)

    events = add_plan_wire.decide(
        state=state,
        command=AddPlanWire(
            plan_id=state.id,
            source_asset_id=cam_a,
            source_port_name="settings_out",
            target_asset_id=sink,
            target_port_name="in",
        ),
        context=context,
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_wire_passes_when_method_is_none_legacy_plan() -> None:
    """Context.method=None disables the role check entirely (legacy
    Plans and tests that predate slice 2)."""
    cam = uuid4()
    sink = uuid4()
    state = _plan_with(
        asset_ids=frozenset({cam, sink}),
        role_bindings=frozenset(),
        method_id=uuid4(),
    )
    image_out = AssetPort(name="image_out", direction=PortDirection.OUTPUT, signal_type="Network")
    sink_in = AssetPort(name="in", direction=PortDirection.INPUT, signal_type="Network")
    assets = {
        cam: _asset(cam, ports=frozenset({image_out})),
        sink: _asset(sink, ports=frozenset({sink_in})),
    }
    context = PlanWireContext(assets=assets, method=None)
    events = add_plan_wire.decide(
        state=state,
        command=AddPlanWire(
            plan_id=state.id,
            source_asset_id=cam,
            source_port_name="image_out",
            target_asset_id=sink,
            target_port_name="in",
        ),
        context=context,
        now=_NOW,
    )
    assert len(events) == 1


def _method_with_trigger_input_role(method_id: UUID, fid: UUID) -> Method:
    return Method(
        id=method_id,
        name=MethodName("m"),
        required_roles=frozenset(
            {
                RoleRequirement(
                    role_name=RoleName("shutter"),
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
        ),
    )


@pytest.mark.unit
def test_wire_target_port_matches_role_required_port_but_wrong_asset_raises() -> None:
    """Symmetric to the source-side scenario: role SHUTTER bound to
    shutter_A on its INPUT port `trigger_in`. Operator tries to wire
    into shutter_B's trigger_in. shutter_B carries the same port name;
    the role check rejects with endpoint_role='target'.
    """
    shutter_a = uuid4()
    shutter_b = uuid4()
    trigger_src = uuid4()
    fid = uuid4()
    method_id = uuid4()
    method = _method_with_trigger_input_role(method_id, fid)
    state = _plan_with(
        asset_ids=frozenset({shutter_a, shutter_b, trigger_src}),
        role_bindings=frozenset(
            {RoleBinding(role_name=RoleName("shutter"), asset_id=shutter_a)},
        ),
        method_id=method_id,
    )
    trigger_in = AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")
    trigger_out = AssetPort(name="trigger_out", direction=PortDirection.OUTPUT, signal_type="TTL")
    assets = {
        shutter_a: _asset(shutter_a, ports=frozenset({trigger_in})),
        shutter_b: _asset(shutter_b, ports=frozenset({trigger_in})),
        trigger_src: _asset(trigger_src, ports=frozenset({trigger_out})),
    }
    context = PlanWireContext(assets=assets, method=method)

    with pytest.raises(PlanWireRoleEndpointMismatchError) as exc:
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=trigger_src,
                source_port_name="trigger_out",
                target_asset_id=shutter_b,
                target_port_name="trigger_in",
            ),
            context=context,
            now=_NOW,
        )
    assert exc.value.endpoint_role == "target"
    assert exc.value.expected_asset_id == shutter_a
    assert exc.value.actual_asset_id == shutter_b


@pytest.mark.unit
def test_wire_passes_when_role_not_yet_bound() -> None:
    """If Method declares a role but no Plan.role_binding exists for
    it yet, the wire's port-name overlap does not conflict (nothing
    to be wrong about). Operators can wire freely before binding;
    `bind_plan_role.decide` scans existing wires symmetrically and
    rejects the bind if it would pin the role to a different Asset
    than the wire's endpoint, so the wire-then-bind ordering is
    closed at the bind step, not here. See
    `PlanWireRoleEndpointMismatchError`."""
    cam = uuid4()
    sink = uuid4()
    fid = uuid4()
    method_id = uuid4()
    method = _method_with_detector_image_out(method_id, fid)
    state = _plan_with(
        asset_ids=frozenset({cam, sink}),
        role_bindings=frozenset(),  # detector NOT bound
        method_id=method_id,
    )
    image_out = AssetPort(name="image_out", direction=PortDirection.OUTPUT, signal_type="Network")
    sink_in = AssetPort(name="in", direction=PortDirection.INPUT, signal_type="Network")
    assets = {
        cam: _asset(cam, ports=frozenset({image_out})),
        sink: _asset(sink, ports=frozenset({sink_in})),
    }
    context = PlanWireContext(assets=assets, method=method)
    events = add_plan_wire.decide(
        state=state,
        command=AddPlanWire(
            plan_id=state.id,
            source_asset_id=cam,
            source_port_name="image_out",
            target_asset_id=sink,
            target_port_name="in",
        ),
        context=context,
        now=_NOW,
    )
    assert len(events) == 1
