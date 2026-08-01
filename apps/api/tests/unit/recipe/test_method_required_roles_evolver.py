"""Unit tests for the Method evolver's handling of MethodRequiredRoleAdded
and MethodRequiredRoleRemoved (slice 1 of the positional role-tagging
workstream).

Pinned: required_roles flows through every existing transition
(MethodVersioned / MethodDeprecated / MethodParametersSchemaUpdated)
without being silently wiped; a regression of the critical
"transition arm preserves additive field" invariant for the new
field. Legacy MethodDefined-only streams fold to required_roles =
frozenset() via the additive-state default.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import PortDirection
from cora.recipe.aggregates.method import (
    MethodStatus,
    PortRequirement,
    RoleName,
    evolve,
    fold,
)
from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodDeprecated,
    MethodParametersSchemaUpdated,
    MethodRequiredRoleAdded,
    MethodRequiredRoleRemoved,
    MethodVersioned,
)

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)


def _genesis(method_id: UUID) -> MethodDefined:
    return MethodDefined(
        method_id=method_id,
        name="Tomography",
        needed_family_ids=(),
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_evolve_method_defined_defaults_required_roles_to_empty() -> None:
    """Legacy MethodDefined streams (and all new ones) start with
    required_roles=frozenset()."""
    state = evolve(None, _genesis(uuid4()))
    assert state.required_roles == frozenset()


@pytest.mark.unit
def test_evolve_required_role_added_folds_into_state() -> None:
    method_id = uuid4()
    family_id = uuid4()
    state = evolve(None, _genesis(method_id))
    state = evolve(
        state,
        MethodRequiredRoleAdded(
            method_id=method_id,
            role_name="detector",
            family_id=family_id,
            required_ports=(
                {
                    "port_name": "trigger_in",
                    "direction": "Input",
                    "signal_type": "TTL",
                },
            ),
            optional=False,
            occurred_at=_NOW,
        ),
    )
    assert len(state.required_roles) == 1
    role = next(iter(state.required_roles))
    assert role.role_name == RoleName("detector")
    assert role.family_id == family_id
    assert role.required_ports == frozenset(
        {PortRequirement("trigger_in", PortDirection.INPUT, "TTL")},
    )
    assert role.optional is False


@pytest.mark.unit
def test_evolve_two_required_roles_added_accumulate() -> None:
    method_id = uuid4()
    family_id_a = uuid4()
    family_id_b = uuid4()
    state = fold(
        [
            _genesis(method_id),
            MethodRequiredRoleAdded(
                method_id=method_id,
                role_name="detector",
                family_id=family_id_a,
                required_ports=(),
                optional=False,
                occurred_at=_NOW,
            ),
            MethodRequiredRoleAdded(
                method_id=method_id,
                role_name="sample_monitor",
                family_id=family_id_b,
                required_ports=(),
                optional=True,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    role_names = {r.role_name.value for r in state.required_roles}
    assert role_names == {"detector", "sample_monitor"}


@pytest.mark.unit
def test_evolve_required_role_removed_drops_by_role_name() -> None:
    method_id = uuid4()
    state = fold(
        [
            _genesis(method_id),
            MethodRequiredRoleAdded(
                method_id=method_id,
                role_name="detector",
                family_id=uuid4(),
                required_ports=(),
                optional=False,
                occurred_at=_NOW,
            ),
            MethodRequiredRoleAdded(
                method_id=method_id,
                role_name="sample_monitor",
                family_id=uuid4(),
                required_ports=(),
                optional=False,
                occurred_at=_NOW,
            ),
            MethodRequiredRoleRemoved(
                method_id=method_id,
                role_name="detector",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    remaining_names = {r.role_name.value for r in state.required_roles}
    assert remaining_names == {"sample_monitor"}


@pytest.mark.unit
def test_evolve_method_versioned_preserves_required_roles() -> None:
    method_id = uuid4()
    family_id = uuid4()
    state = fold(
        [
            _genesis(method_id),
            MethodRequiredRoleAdded(
                method_id=method_id,
                role_name="detector",
                family_id=family_id,
                required_ports=(),
                optional=False,
                occurred_at=_NOW,
            ),
            MethodVersioned(
                method_id=method_id,
                version_tag="v1",
                occurred_at=_NOW,
                content_hash="0" * 64,
            ),
        ]
    )
    assert state is not None
    assert state.status is MethodStatus.VERSIONED
    role_names = {r.role_name.value for r in state.required_roles}
    assert role_names == {"detector"}


@pytest.mark.unit
def test_evolve_method_deprecated_preserves_required_roles() -> None:
    method_id = uuid4()
    state = fold(
        [
            _genesis(method_id),
            MethodRequiredRoleAdded(
                method_id=method_id,
                role_name="detector",
                family_id=uuid4(),
                required_ports=(),
                optional=False,
                occurred_at=_NOW,
            ),
            MethodDeprecated(reason="Superseded", method_id=method_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is MethodStatus.DEPRECATED
    role_names = {r.role_name.value for r in state.required_roles}
    assert role_names == {"detector"}


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_preserves_required_roles() -> None:
    method_id = uuid4()
    state = fold(
        [
            _genesis(method_id),
            MethodRequiredRoleAdded(
                method_id=method_id,
                role_name="detector",
                family_id=uuid4(),
                required_ports=(),
                optional=False,
                occurred_at=_NOW,
            ),
            MethodParametersSchemaUpdated(
                method_id=method_id,
                parameters_schema={"type": "object", "properties": {}},
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    role_names = {r.role_name.value for r in state.required_roles}
    assert role_names == {"detector"}


@pytest.mark.unit
def test_evolve_legacy_method_defined_only_stream_folds_with_empty_required_roles() -> None:
    """A MethodDefined-only stream (no role events ever emitted) folds
    cleanly to required_roles=frozenset() via the additive-state default.
    Pin so the field's default never silently disappears in a future
    refactor."""
    state = fold([_genesis(uuid4())])
    assert state is not None
    assert state.required_roles == frozenset()


@pytest.mark.unit
def test_evolve_required_role_added_reconstructs_port_direction_enum() -> None:
    """The payload carries direction as a string ('Input' / 'Output');
    the evolver hydrates it back to the PortDirection enum so the
    PortRequirement VO inside state is always typed."""
    method_id = uuid4()
    state = fold(
        [
            _genesis(method_id),
            MethodRequiredRoleAdded(
                method_id=method_id,
                role_name="detector",
                family_id=uuid4(),
                required_ports=(
                    {
                        "port_name": "data_out",
                        "direction": "Output",
                        "signal_type": "Network",
                    },
                ),
                optional=False,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    role = next(iter(state.required_roles))
    port = next(iter(role.required_ports))
    assert port.direction is PortDirection.OUTPUT
