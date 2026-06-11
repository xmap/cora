"""Architecture-fitness tests pinning the slice-1 scope of the
positional role-tagging workstream.

Pins what slice 1 ships and what it deliberately defers, so a
future refactor that conflates slice 1 with slice 2 (Plan-side role
bindings + Wire-role-endpoint invariant) trips a clear test name.
See [[project-method-required-roles-design]] §"Slice plan".

Also pins the cross-BC type-reuse documentation: the
`PortDirection` enum from Equipment BC is the ONLY new cross-BC
type dependency added by slice 1.
"""

import inspect
from pathlib import Path

import pytest

from cora.recipe.aggregates.method import RoleRequirement
from cora.recipe.aggregates.method import state as method_state
from cora.recipe.features import add_method_required_role, remove_method_required_role


@pytest.mark.architecture
def test_add_slice_directory_has_six_files() -> None:
    """Slice 1 ships the canonical 6-file slice topology
    (__init__, command, decider, handler, route, tool), same shape
    as add_asset_owner and update_method_parameters_schema. Catches a
    refactor that accidentally adds an extra file or drops one."""
    slice_dir = Path(add_method_required_role.__file__).parent
    py_files = sorted(p.name for p in slice_dir.glob("*.py"))
    assert py_files == [
        "__init__.py",
        "command.py",
        "decider.py",
        "handler.py",
        "route.py",
        "tool.py",
    ]


@pytest.mark.architecture
def test_remove_slice_directory_has_six_files() -> None:
    """R2 symmetry: remove slice mirrors add slice's 6-file shape."""
    slice_dir = Path(remove_method_required_role.__file__).parent
    py_files = sorted(p.name for p in slice_dir.glob("*.py"))
    assert py_files == [
        "__init__.py",
        "command.py",
        "decider.py",
        "handler.py",
        "route.py",
        "tool.py",
    ]


@pytest.mark.architecture
def test_role_requirement_carries_required_ports_field() -> None:
    """Pins that RoleRequirement carries `required_ports` (the
    structural closure the 2026-06-06 critique demanded). A future
    refactor that drops the field would silently re-introduce the
    role-table-vs-wire-graph divergence Option A was originally
    refuted on. Layer 3 sub-slice 3D widens the VO with the XOR-
    bound `role_kind` field (federation-portable path) alongside
    the slice-1 `family_id` field (anatomical escape hatch)."""
    field_names = {f for f in RoleRequirement.__dataclass_fields__}
    assert "required_ports" in field_names
    assert "role_name" in field_names
    assert "family_id" in field_names
    assert "optional" in field_names
    # Layer 3 3D additive field. XOR with family_id enforced by VO
    # __post_init__.
    assert "role_kind" in field_names


@pytest.mark.architecture
def test_method_state_reuses_port_direction_from_equipment_bc() -> None:
    """The PortDirection enum from Equipment BC is the ONLY new cross-
    BC type dependency added by slice 1, and Layer 3 sub-slice 3D
    deliberately preserves this minimal surface: `RoleRequirement.role_kind`
    types as bare `UUID` rather than the `RoleId` NewType (per the 3D
    design memo's cross-BC NewType-avoidance rule), so 3D adds NO new
    cora.equipment import to Method state.py. Symmetric with the
    pre-existing `family_id: UUID` field.

    A future addition of a new cora.equipment import line would
    surface here and require explicit design review (per
    project_bc_map.md)."""
    source = inspect.getsource(method_state)
    # Positive: PortDirection + two length constants ARE imported.
    assert "PortDirection" in source
    assert "PORT_NAME_MAX_LENGTH" in source
    assert "PORT_SIGNAL_TYPE_MAX_LENGTH" in source
    # Negative: no other cora.equipment surface leaks into state.py.
    cross_bc_lines = [
        line for line in source.splitlines() if line.strip().startswith("from cora.equipment")
    ]
    assert len(cross_bc_lines) == 1, (
        f"Expected exactly one cora.equipment import line in Method "
        f"state.py; found {len(cross_bc_lines)}: {cross_bc_lines}"
    )


@pytest.mark.architecture
def test_add_plan_wire_decider_enforces_role_endpoint_check() -> None:
    """The add_plan_wire decider MUST reference
    PlanWireRoleEndpointMismatchError and walk Method.required_roles
    against Plan.role_bindings to prevent role-table-vs-wire-graph
    divergence. Pin so a future refactor that drops the role check
    trips a clearly-named test (the bug the 2026-06-06 critique
    surfaced)."""
    from cora.recipe.features.add_plan_wire import decider as add_plan_wire_decider

    source = inspect.getsource(add_plan_wire_decider)
    assert "PlanWireRoleEndpointMismatchError" in source, (
        "add_plan_wire decider must enforce the role-endpoint check (structural closure)"
    )
    assert "required_roles" in source, (
        "add_plan_wire decider must walk Method.required_roles to validate role-port consistency"
    )
    assert "role_bindings" in source, (
        "add_plan_wire decider must compare against Plan.role_bindings "
        "to identify the role's bound Asset"
    )


@pytest.mark.architecture
def test_bind_plan_role_decider_enforces_role_endpoint_check() -> None:
    """The bind_plan_role decider MUST raise
    PlanWireRoleEndpointMismatchError when an existing wire claims the
    role's required port at a different Asset. The companion to the
    add_plan_wire pin above: together they close BOTH temporal
    orderings (bind-then-wire AND wire-then-bind / unbind-rebind)."""
    from cora.recipe.features.bind_plan_role import decider as bind_plan_role_decider

    source = inspect.getsource(bind_plan_role_decider)
    assert "PlanWireRoleEndpointMismatchError" in source, (
        "bind_plan_role decider must enforce the symmetric role-endpoint check; "
        "without it, wire-then-bind and unbind-rebind orderings silently diverge "
        "the role table from the wire graph"
    )
    assert "state.wires" in source, (
        "bind_plan_role decider must scan state.wires for endpoints that already "
        "claim a required_port of the role being bound"
    )


@pytest.mark.architecture
def test_bind_plan_role_decider_rejects_wire_then_bind_ordering_behaviorally() -> None:
    """Behavior-level companion to the source-string pins above: the
    role-endpoint closure is exercised by constructing a minimal Plan
    with an existing wire on a different Asset than the candidate
    binding, calling decide(), and asserting the raise. A future
    refactor that keeps the substring `PlanWireRoleEndpointMismatchError`
    in the source but no longer raises (e.g. behind a feature flag,
    inside a dead branch) would slip past the source-string pin; this
    test catches that drift."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from cora.equipment.aggregates.asset import (
        Asset,
        AssetName,
        AssetPort,
        AssetTier,
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
        Wire,
    )
    from cora.recipe.features import bind_plan_role
    from cora.recipe.features.bind_plan_role import BindPlanRole, BindPlanRoleContext

    candidate_aid = uuid4()
    wire_aid = uuid4()
    fid = uuid4()
    method_id = uuid4()
    plan_id = uuid4()
    method = Method(
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
                                port_name="data_out",
                                direction=PortDirection.OUTPUT,
                                signal_type="frame",
                            ),
                        }
                    ),
                ),
            }
        ),
    )
    state = Plan(
        id=plan_id,
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=frozenset({candidate_aid, wire_aid}),
        status=PlanStatus.DEFINED,
        method_id=method_id,
        wires=frozenset(
            {
                Wire(
                    source_asset_id=wire_aid,
                    source_port_name="data_out",
                    target_asset_id=uuid4(),
                    target_port_name="data_in",
                ),
            }
        ),
    )
    asset = Asset(
        id=candidate_aid,
        name=AssetName("a"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=frozenset({fid}),
        ports=frozenset(
            {AssetPort(name="data_out", direction=PortDirection.OUTPUT, signal_type="frame")}
        ),
    )
    with pytest.raises(PlanWireRoleEndpointMismatchError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(
                plan_id=plan_id,
                role_name=RoleName("detector"),
                asset_id=candidate_aid,
            ),
            context=BindPlanRoleContext(method=method, asset=asset),
            now=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
        )
