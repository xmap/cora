"""Unit tests pinning the RoleRequirement XOR invariant (Layer 3 3D)."""

from uuid import uuid4

import pytest

from cora.recipe.aggregates.method import (
    InvalidRoleRequirementTargetError,
    PortRequirement,
    RoleName,
    RoleRequirement,
    RoleRequirementBindingDuplicateError,
)


@pytest.mark.unit
def test_role_requirement_accepts_family_id_only_slice_1_shape() -> None:
    fid = uuid4()
    req = RoleRequirement(role_name=RoleName("DETECTOR"), family_id=fid)
    assert req.family_id == fid
    assert req.role_kind is None


@pytest.mark.unit
def test_role_requirement_accepts_role_kind_only_3d_shape() -> None:
    rid = uuid4()
    req = RoleRequirement(role_name=RoleName("DETECTOR"), role_kind=rid)
    assert req.role_kind == rid
    assert req.family_id is None


@pytest.mark.unit
def test_role_requirement_raises_when_both_set() -> None:
    fid = uuid4()
    rid = uuid4()
    with pytest.raises(RoleRequirementBindingDuplicateError) as exc:
        RoleRequirement(
            role_name=RoleName("DETECTOR"),
            role_kind=rid,
            family_id=fid,
        )
    assert exc.value.role_kind == rid
    assert exc.value.family_id == fid


@pytest.mark.unit
def test_role_requirement_raises_when_neither_set() -> None:
    with pytest.raises(InvalidRoleRequirementTargetError) as exc:
        RoleRequirement(role_name=RoleName("DETECTOR"))
    assert exc.value.role_name == RoleName("DETECTOR")


@pytest.mark.unit
def test_role_requirement_keeps_required_ports_independent_of_xor() -> None:
    """required_ports + optional are orthogonal to the XOR pair."""
    ports = frozenset(
        {
            PortRequirement(
                port_name="out",
                direction=__import__(
                    "cora.equipment.aggregates.asset", fromlist=["PortDirection"]
                ).PortDirection.OUTPUT,
                signal_type="TTL",
            )
        }
    )
    req_role = RoleRequirement(
        role_name=RoleName("DETECTOR"),
        role_kind=uuid4(),
        required_ports=ports,
        optional=True,
    )
    assert len(req_role.required_ports) == 1
    assert req_role.optional is True
    req_family = RoleRequirement(
        role_name=RoleName("DETECTOR"),
        family_id=uuid4(),
        required_ports=ports,
        optional=True,
    )
    assert len(req_family.required_ports) == 1
    assert req_family.optional is True


@pytest.mark.unit
def test_role_requirement_subclasses_value_error() -> None:
    """Both new errors are ValueError subclasses (VO-error convention)."""
    assert issubclass(RoleRequirementBindingDuplicateError, ValueError)
    assert issubclass(InvalidRoleRequirementTargetError, ValueError)
