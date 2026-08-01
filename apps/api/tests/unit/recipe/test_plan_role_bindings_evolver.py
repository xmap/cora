"""Evolver tests for PlanRoleBound / PlanRoleUnbound + preservation
of role_bindings across PlanVersioned / PlanDeprecated /
PlanDefaultParametersUpdated / PlanWireAdded / PlanWireRemoved
(slice 2 of positional role-tagging)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.method import RoleName
from cora.recipe.aggregates.plan import RoleBinding, evolve, fold
from cora.recipe.aggregates.plan.events import (
    PlanDefaultParametersUpdated,
    PlanDefined,
    PlanDeprecated,
    PlanRoleBound,
    PlanRoleUnbound,
    PlanVersioned,
    PlanWireAdded,
    PlanWireRemoved,
)

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)


def _genesis(plan_id: UUID, asset_id: UUID) -> PlanDefined:
    return PlanDefined(
        plan_id=plan_id,
        name="p",
        practice_id=uuid4(),
        asset_ids=(asset_id,),
        method_id=uuid4(),
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={},
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_plan_defined_defaults_role_bindings_to_empty() -> None:
    state = evolve(None, _genesis(uuid4(), uuid4()))
    assert state.role_bindings == frozenset()


@pytest.mark.unit
def test_evolve_role_bound_folds_into_state() -> None:
    plan_id = uuid4()
    asset_id = uuid4()
    state = fold(
        [
            _genesis(plan_id, asset_id),
            PlanRoleBound(
                plan_id=plan_id,
                role_name="detector",
                asset_id=asset_id,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.role_bindings == frozenset(
        {RoleBinding(role_name=RoleName("detector"), asset_id=asset_id)},
    )


@pytest.mark.unit
def test_evolve_two_role_bindings_accumulate() -> None:
    plan_id = uuid4()
    a1, a2 = uuid4(), uuid4()
    state = fold(
        [
            _genesis(plan_id, a1),
            PlanRoleBound(plan_id=plan_id, role_name="detector", asset_id=a1, occurred_at=_NOW),
            PlanRoleBound(
                plan_id=plan_id, role_name="sample_monitor", asset_id=a2, occurred_at=_NOW
            ),
        ]
    )
    assert state is not None
    role_names = {b.role_name.value for b in state.role_bindings}
    assert role_names == {"detector", "sample_monitor"}


@pytest.mark.unit
def test_evolve_role_unbound_drops_by_role_name() -> None:
    plan_id = uuid4()
    a1 = uuid4()
    state = fold(
        [
            _genesis(plan_id, a1),
            PlanRoleBound(plan_id=plan_id, role_name="detector", asset_id=a1, occurred_at=_NOW),
            PlanRoleBound(
                plan_id=plan_id, role_name="sample_monitor", asset_id=a1, occurred_at=_NOW
            ),
            PlanRoleUnbound(plan_id=plan_id, role_name="detector", occurred_at=_NOW),
        ]
    )
    assert state is not None
    role_names = {b.role_name.value for b in state.role_bindings}
    assert role_names == {"sample_monitor"}


@pytest.mark.unit
def test_role_bindings_preserved_through_plan_versioned() -> None:
    plan_id = uuid4()
    a1 = uuid4()
    state = fold(
        [
            _genesis(plan_id, a1),
            PlanRoleBound(plan_id=plan_id, role_name="detector", asset_id=a1, occurred_at=_NOW),
            PlanVersioned(
                plan_id=plan_id,
                version_tag="v1",
                occurred_at=_NOW,
                content_hash="0" * 64,
            ),
        ]
    )
    assert state is not None
    assert {b.role_name.value for b in state.role_bindings} == {"detector"}


@pytest.mark.unit
def test_role_bindings_preserved_through_plan_deprecated() -> None:
    plan_id = uuid4()
    a1 = uuid4()
    state = fold(
        [
            _genesis(plan_id, a1),
            PlanRoleBound(plan_id=plan_id, role_name="detector", asset_id=a1, occurred_at=_NOW),
            PlanDeprecated(reason="Superseded", plan_id=plan_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert {b.role_name.value for b in state.role_bindings} == {"detector"}


@pytest.mark.unit
def test_role_bindings_preserved_through_default_parameters_updated() -> None:
    plan_id = uuid4()
    a1 = uuid4()
    state = fold(
        [
            _genesis(plan_id, a1),
            PlanRoleBound(plan_id=plan_id, role_name="detector", asset_id=a1, occurred_at=_NOW),
            PlanDefaultParametersUpdated(
                plan_id=plan_id,
                default_parameters={"k": "v"},
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert {b.role_name.value for b in state.role_bindings} == {"detector"}


@pytest.mark.unit
def test_role_bindings_preserved_through_wire_added_and_removed() -> None:
    plan_id = uuid4()
    a1, a2 = uuid4(), uuid4()
    state = fold(
        [
            _genesis(plan_id, a1),
            PlanRoleBound(plan_id=plan_id, role_name="detector", asset_id=a1, occurred_at=_NOW),
            PlanWireAdded(
                plan_id=plan_id,
                source_asset_id=a1,
                source_port_name="out",
                target_asset_id=a2,
                target_port_name="in",
                occurred_at=_NOW,
            ),
            PlanWireRemoved(
                plan_id=plan_id,
                source_asset_id=a1,
                source_port_name="out",
                target_asset_id=a2,
                target_port_name="in",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert {b.role_name.value for b in state.role_bindings} == {"detector"}


@pytest.mark.unit
def test_legacy_plan_defined_only_stream_folds_with_empty_role_bindings() -> None:
    state = fold([_genesis(uuid4(), uuid4())])
    assert state is not None
    assert state.role_bindings == frozenset()
