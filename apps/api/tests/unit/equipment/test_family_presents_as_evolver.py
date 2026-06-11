"""Evolver tests for the Family presents_as add/remove arms (Layer 3 3B)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family import (
    Affordance,
    FamilyDefined,
    FamilyDeprecated,
    FamilyPresentsAsAdded,
    FamilyPresentsAsRemoved,
    FamilySettingsSchemaUpdated,
    FamilyStatus,
    FamilyVersioned,
    evolve,
    fold,
)

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _defined(
    family_id: UUID,
    affordances: frozenset[Affordance] = frozenset(),
) -> FamilyDefined:
    return FamilyDefined(
        family_id=family_id,
        name="Camera",
        occurred_at=_NOW,
        affordances=affordances,
    )


@pytest.mark.unit
def test_family_genesis_starts_with_empty_presents_as() -> None:
    fid = uuid4()
    state = evolve(None, _defined(fid))
    assert state.presents_as == frozenset()


@pytest.mark.unit
def test_presents_as_added_appends_role_id() -> None:
    fid = uuid4()
    rid = uuid4()
    state = fold(
        [
            _defined(fid),
            FamilyPresentsAsAdded(family_id=fid, role_id=rid, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert RoleId(rid) in state.presents_as


@pytest.mark.unit
def test_presents_as_added_twice_with_distinct_roles_collects_both() -> None:
    fid = uuid4()
    rid_a = uuid4()
    rid_b = uuid4()
    state = fold(
        [
            _defined(fid),
            FamilyPresentsAsAdded(family_id=fid, role_id=rid_a, occurred_at=_NOW),
            FamilyPresentsAsAdded(family_id=fid, role_id=rid_b, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.presents_as == frozenset({RoleId(rid_a), RoleId(rid_b)})


@pytest.mark.unit
def test_presents_as_removed_drops_role_id() -> None:
    fid = uuid4()
    rid = uuid4()
    state = fold(
        [
            _defined(fid),
            FamilyPresentsAsAdded(family_id=fid, role_id=rid, occurred_at=_NOW),
            FamilyPresentsAsRemoved(family_id=fid, role_id=rid, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.presents_as == frozenset()


@pytest.mark.unit
def test_presents_as_preserved_across_version() -> None:
    """A new version replaces affordances but presents_as is preserved."""
    fid = uuid4()
    rid = uuid4()
    state = fold(
        [
            _defined(fid, affordances=frozenset({Affordance.IMAGEABLE})),
            FamilyPresentsAsAdded(family_id=fid, role_id=rid, occurred_at=_NOW),
            FamilyVersioned(
                family_id=fid,
                version_tag="v2",
                occurred_at=_NOW,
                affordances=frozenset({Affordance.IMAGEABLE, Affordance.STREAMABLE}),
            ),
        ]
    )
    assert state is not None
    assert state.status is FamilyStatus.VERSIONED
    assert RoleId(rid) in state.presents_as


@pytest.mark.unit
def test_presents_as_preserved_across_deprecation() -> None:
    fid = uuid4()
    rid = uuid4()
    state = fold(
        [
            _defined(fid),
            FamilyPresentsAsAdded(family_id=fid, role_id=rid, occurred_at=_NOW),
            FamilyDeprecated(family_id=fid, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is FamilyStatus.DEPRECATED
    assert RoleId(rid) in state.presents_as


@pytest.mark.unit
def test_presents_as_preserved_across_settings_schema_update() -> None:
    fid = uuid4()
    rid = uuid4()
    state = fold(
        [
            _defined(fid),
            FamilyPresentsAsAdded(family_id=fid, role_id=rid, occurred_at=_NOW),
            FamilySettingsSchemaUpdated(
                family_id=fid,
                settings_schema={
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                },
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert RoleId(rid) in state.presents_as
