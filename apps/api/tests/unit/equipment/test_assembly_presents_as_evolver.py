"""Evolver tests for the Assembly presents_as add/remove arms (Layer 3 3C)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    AssemblyDefined,
    AssemblyDeprecated,
    AssemblyName,
    AssemblyPresentsAsAdded,
    AssemblyPresentsAsRemoved,
    AssemblyStatus,
    AssemblyVersioned,
    evolve,
    fold,
)

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _defined(assembly_id: UUID, family_id: UUID) -> AssemblyDefined:
    return AssemblyDefined(
        assembly_id=assembly_id,
        name=AssemblyName("MCTOptics"),
        presents_as_family_id=family_id,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash="abc",
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_assembly_genesis_starts_with_empty_presents_as() -> None:
    aid = uuid4()
    state = evolve(None, _defined(aid, uuid4()))
    assert state.presents_as == frozenset()


@pytest.mark.unit
def test_presents_as_added_appends_role_id() -> None:
    aid = uuid4()
    rid = uuid4()
    state = fold(
        [
            _defined(aid, uuid4()),
            AssemblyPresentsAsAdded(assembly_id=aid, role_id=rid, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert RoleId(rid) in state.presents_as


@pytest.mark.unit
def test_presents_as_removed_drops_role_id() -> None:
    aid = uuid4()
    rid = uuid4()
    state = fold(
        [
            _defined(aid, uuid4()),
            AssemblyPresentsAsAdded(assembly_id=aid, role_id=rid, occurred_at=_NOW),
            AssemblyPresentsAsRemoved(assembly_id=aid, role_id=rid, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.presents_as == frozenset()


@pytest.mark.unit
def test_presents_as_preserved_across_version() -> None:
    """A new version replaces structural fields but presents_as is preserved."""
    aid = uuid4()
    rid = uuid4()
    fam = uuid4()
    state = fold(
        [
            _defined(aid, fam),
            AssemblyPresentsAsAdded(assembly_id=aid, role_id=rid, occurred_at=_NOW),
            AssemblyVersioned(
                assembly_id=aid,
                name=AssemblyName("MCTOptics"),
                presents_as_family_id=fam,
                required_slots=frozenset(),
                required_wires=frozenset(),
                parameter_overrides_schema=None,
                drawing=None,
                version="v2",
                content_hash="def",
                previous_content_hash="abc",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status is AssemblyStatus.VERSIONED
    assert RoleId(rid) in state.presents_as


@pytest.mark.unit
def test_presents_as_preserved_across_deprecation() -> None:
    aid = uuid4()
    rid = uuid4()
    state = fold(
        [
            _defined(aid, uuid4()),
            AssemblyPresentsAsAdded(assembly_id=aid, role_id=rid, occurred_at=_NOW),
            AssemblyDeprecated(assembly_id=aid, reason="retired", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is AssemblyStatus.DEPRECATED
    assert RoleId(rid) in state.presents_as


@pytest.mark.unit
def test_multiple_roles_co_accumulate() -> None:
    aid = uuid4()
    rid_a = uuid4()
    rid_b = uuid4()
    state = fold(
        [
            _defined(aid, uuid4()),
            AssemblyPresentsAsAdded(assembly_id=aid, role_id=rid_a, occurred_at=_NOW),
            AssemblyPresentsAsAdded(assembly_id=aid, role_id=rid_b, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.presents_as == frozenset({RoleId(rid_a), RoleId(rid_b)})


@pytest.mark.unit
def test_presents_as_not_in_content_subset() -> None:
    """3C: presents_as is orthogonal-axis additive; NOT part of content_hash."""
    aid = uuid4()
    rid = uuid4()
    state = fold(
        [
            _defined(aid, uuid4()),
            AssemblyPresentsAsAdded(assembly_id=aid, role_id=rid, occurred_at=_NOW),
        ]
    )
    assert state is not None
    subset = state.content_subset()
    assert "presents_as" not in subset
