"""Layer 3 sub-slice 3D: decider tests for the role_kind path of `add_method_required_role`.

The decider does NOT verify the Role exists (that's the handler-
side RoleLookup precondition); these tests pin that a role_kind-
bearing RoleRequirement folds cleanly through the decider and the
emitted event carries `role_kind` rather than `family_id`.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.method import (
    MethodCannotMutateRequiredRolesError,
    MethodNotFoundError,
    MethodRequiredRoleAdded,
    MethodRoleNameAlreadyDeclaredError,
    MethodStatus,
    RoleName,
    RoleRequirement,
)
from cora.recipe.aggregates.method.state import Method, MethodName
from cora.recipe.features import add_method_required_role
from cora.recipe.features.add_method_required_role import AddMethodRequiredRole

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _method(
    method_id: UUID,
    *,
    required_roles: frozenset[RoleRequirement] = frozenset(),
    status: MethodStatus = MethodStatus.DEFINED,
) -> Method:
    return Method(
        id=method_id,
        name=MethodName("Tomography"),
        status=status,
        required_roles=required_roles,
    )


@pytest.mark.unit
def test_decide_emits_role_kind_event_for_role_kind_only_requirement() -> None:
    mid = uuid4()
    rid = uuid4()
    requirement = RoleRequirement(role_name=RoleName("DETECTOR"), role_kind=rid)
    events = add_method_required_role.decide(
        state=_method(mid),
        command=AddMethodRequiredRole(method_id=mid, requirement=requirement),
        now=_NOW,
    )
    assert events == [
        MethodRequiredRoleAdded(
            method_id=mid,
            role_name="DETECTOR",
            family_id=None,
            required_ports=(),
            optional=False,
            occurred_at=_NOW,
            role_kind=rid,
        )
    ]


@pytest.mark.unit
def test_decide_emits_family_id_event_for_slice_1_requirement() -> None:
    """Backward compatibility: a slice-1 family_id-only RoleRequirement
    folds into an event with role_kind=None + family_id set."""
    mid = uuid4()
    fid = uuid4()
    requirement = RoleRequirement(role_name=RoleName("DETECTOR"), family_id=fid)
    events = add_method_required_role.decide(
        state=_method(mid),
        command=AddMethodRequiredRole(method_id=mid, requirement=requirement),
        now=_NOW,
    )
    assert events[0].role_kind is None
    assert events[0].family_id == fid


@pytest.mark.unit
def test_decide_role_kind_path_still_rejects_duplicate_role_name() -> None:
    """Strict-not-idempotent applies regardless of XOR target."""
    mid = uuid4()
    rid = uuid4()
    existing = RoleRequirement(role_name=RoleName("DETECTOR"), family_id=uuid4())
    state = _method(mid, required_roles=frozenset({existing}))
    duplicate = RoleRequirement(role_name=RoleName("DETECTOR"), role_kind=rid)
    with pytest.raises(MethodRoleNameAlreadyDeclaredError):
        add_method_required_role.decide(
            state=state,
            command=AddMethodRequiredRole(method_id=mid, requirement=duplicate),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_role_kind_path_rejects_versioned_method() -> None:
    """Lifecycle guard fires before any role_kind-specific logic."""
    mid = uuid4()
    rid = uuid4()
    state = _method(mid, status=MethodStatus.VERSIONED)
    requirement = RoleRequirement(role_name=RoleName("DETECTOR"), role_kind=rid)
    with pytest.raises(MethodCannotMutateRequiredRolesError):
        add_method_required_role.decide(
            state=state,
            command=AddMethodRequiredRole(method_id=mid, requirement=requirement),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_role_kind_path_rejects_missing_method() -> None:
    mid = uuid4()
    rid = uuid4()
    requirement = RoleRequirement(role_name=RoleName("DETECTOR"), role_kind=rid)
    with pytest.raises(MethodNotFoundError):
        add_method_required_role.decide(
            state=None,
            command=AddMethodRequiredRole(method_id=mid, requirement=requirement),
            now=_NOW,
        )
