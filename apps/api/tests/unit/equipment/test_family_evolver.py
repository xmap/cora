"""Unit tests for the Family aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.family import (
    Affordance,
    Family,
    FamilyName,
    FamilyStatus,
    evolve,
    fold,
)
from cora.equipment.aggregates.family.events import (
    FamilyDefined,
    FamilyDeprecated,
    FamilySettingsSchemaUpdated,
    FamilyVersioned,
)
from cora.equipment.features import define_family
from cora.equipment.features.define_family import DefineFamily

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_capability_defined_sets_status_to_defined() -> None:
    """FamilyDefined is the genesis event; status defaults to
    Defined via the evolver. Pin so a future change (for example adding
    `initial_status` to the event payload) is a deliberate
    additive-state evolution."""
    family_id = uuid4()
    state = evolve(
        None,
        FamilyDefined(family_id=family_id, name="Tomography", occurred_at=_NOW),
    )
    assert state == Family(id=family_id, name=FamilyName("Tomography"), status=FamilyStatus.DEFINED)


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_capability_defined_returns_capability() -> None:
    family_id = uuid4()
    state = fold([FamilyDefined(family_id=family_id, name="Tomography", occurred_at=_NOW)])
    assert state == Family(id=family_id, name=FamilyName("Tomography"), status=FamilyStatus.DEFINED)


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    family_id = uuid4()
    events = [FamilyDefined(family_id=family_id, name="Tomography", occurred_at=_NOW)]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state."""
    new_id = uuid4()
    command = DefineFamily(
        name="  Tomography  ", affordances=frozenset()
    )  # whitespace exercises the VO trim

    events = define_family.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)

    assert rebuilt == Family(id=new_id, name=FamilyName("Tomography"), status=FamilyStatus.DEFINED)


# ---------- FamilyVersioned ----------


@pytest.mark.unit
def test_evolve_capability_defined_starts_with_null_version() -> None:
    """Genesis-only stream folds with version=None
    (additive-state pattern: streams without the new field fold cleanly without
    an upcaster)."""
    state = evolve(
        None,
        FamilyDefined(family_id=uuid4(), name="X", occurred_at=_NOW),
    )
    assert state.version is None


@pytest.mark.unit
def test_evolve_capability_versioned_flips_status_and_sets_version() -> None:
    family_id = uuid4()
    defined = Family(
        id=family_id,
        name=FamilyName("Tomography"),
        status=FamilyStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        FamilyVersioned(family_id=family_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.status is FamilyStatus.VERSIONED
    assert versioned.version == "v2"
    # Other state preserved.
    assert versioned.id == family_id
    assert versioned.name == FamilyName("Tomography")


@pytest.mark.unit
def test_evolve_capability_versioned_replaces_prior_version_tag() -> None:
    """Subsequent revisions overwrite version with the new
    label. Pinned: the latest version is what version reflects."""
    family_id = uuid4()
    versioned_v1 = Family(
        id=family_id,
        name=FamilyName("X"),
        status=FamilyStatus.VERSIONED,
        version="v1",
    )
    versioned_v2 = evolve(
        versioned_v1,
        FamilyVersioned(family_id=family_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned_v2.version == "v2"


@pytest.mark.unit
def test_evolve_capability_versioned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            FamilyVersioned(family_id=uuid4(), version_tag="v1", occurred_at=_NOW),
        )


# ---------- FamilyDeprecated ----------


@pytest.mark.unit
def test_evolve_capability_deprecated_flips_status_and_preserves_version() -> None:
    """Version is preserved across deprecation — the
    historical label of when the capability was last revised remains
    visible. Pinned: a future change that wiped version on
    deprecation would lose the audit signal."""
    family_id = uuid4()
    versioned = Family(
        id=family_id,
        name=FamilyName("X"),
        status=FamilyStatus.VERSIONED,
        version="v3",
    )
    deprecated = evolve(
        versioned,
        FamilyDeprecated(reason="Superseded", family_id=family_id, occurred_at=_NOW),
    )
    assert deprecated.status is FamilyStatus.DEPRECATED
    assert deprecated.version == "v3"


@pytest.mark.unit
def test_evolve_capability_deprecated_from_defined_preserves_null_version() -> None:
    """Deprecating a Defined-only capability (never versioned) keeps
    version=None."""
    defined = Family(
        id=uuid4(),
        name=FamilyName("X"),
        status=FamilyStatus.DEFINED,
    )
    deprecated = evolve(
        defined,
        FamilyDeprecated(reason="Superseded", family_id=defined.id, occurred_at=_NOW),
    )
    assert deprecated.status is FamilyStatus.DEPRECATED
    assert deprecated.version is None


@pytest.mark.unit
def test_evolve_capability_deprecated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, FamilyDeprecated(reason="Superseded", family_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_define_version_yields_versioned_capability() -> None:
    family_id = uuid4()
    state = fold(
        [
            FamilyDefined(family_id=family_id, name="X", occurred_at=_NOW),
            FamilyVersioned(family_id=family_id, version_tag="v2", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is FamilyStatus.VERSIONED
    assert state.version == "v2"


@pytest.mark.unit
def test_fold_define_version_version_yields_latest_version_tag() -> None:
    """Multi-revision fold: latest version_tag wins."""
    family_id = uuid4()
    state = fold(
        [
            FamilyDefined(family_id=family_id, name="X", occurred_at=_NOW),
            FamilyVersioned(family_id=family_id, version_tag="v1", occurred_at=_NOW),
            FamilyVersioned(family_id=family_id, version_tag="v2", occurred_at=_NOW),
            FamilyVersioned(family_id=family_id, version_tag="v3", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.version == "v3"


@pytest.mark.unit
def test_fold_define_deprecate_yields_deprecated_capability() -> None:
    family_id = uuid4()
    state = fold(
        [
            FamilyDefined(family_id=family_id, name="X", occurred_at=_NOW),
            FamilyDeprecated(reason="Superseded", family_id=family_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is FamilyStatus.DEPRECATED


@pytest.mark.unit
def test_fold_define_version_deprecate_preserves_version_through_deprecation() -> None:
    """Full lifecycle audit: define → version → deprecate keeps the
    last version_tag as a historical record on the deprecated state."""
    family_id = uuid4()
    state = fold(
        [
            FamilyDefined(family_id=family_id, name="X", occurred_at=_NOW),
            FamilyVersioned(family_id=family_id, version_tag="v2", occurred_at=_NOW),
            FamilyDeprecated(reason="Superseded", family_id=family_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is FamilyStatus.DEPRECATED
    assert state.version == "v2"


# ---- settings_schema folding ---------------------------------


_TEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
}


@pytest.mark.unit
def test_capability_defined_starts_with_no_settings_schema() -> None:
    """Pre-5g-a additive-state default: a Family without any
    schema-update event has settings_schema=None."""
    family_id = uuid4()
    state = fold([FamilyDefined(family_id=family_id, name="X", occurred_at=_NOW)])
    assert state is not None
    assert state.settings_schema is None


@pytest.mark.unit
def test_capability_settings_schema_updated_sets_schema() -> None:
    family_id = uuid4()
    state = fold(
        [
            FamilyDefined(family_id=family_id, name="X", occurred_at=_NOW),
            FamilySettingsSchemaUpdated(
                family_id=family_id,
                settings_schema=_TEST_SCHEMA,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.settings_schema == _TEST_SCHEMA


@pytest.mark.unit
def test_capability_settings_schema_updated_with_none_clears_schema() -> None:
    """Operator explicitly removes a previously-declared schema."""
    family_id = uuid4()
    state = fold(
        [
            FamilyDefined(family_id=family_id, name="X", occurred_at=_NOW),
            FamilySettingsSchemaUpdated(
                family_id=family_id,
                settings_schema=_TEST_SCHEMA,
                occurred_at=_NOW,
            ),
            FamilySettingsSchemaUpdated(
                family_id=family_id,
                settings_schema=None,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.settings_schema is None


@pytest.mark.unit
def test_settings_schema_preserved_across_versioning() -> None:
    """Schema iteration is independent of content versioning;
    FamilyVersioned must NOT clobber a previously-set schema."""
    family_id = uuid4()
    state = fold(
        [
            FamilyDefined(family_id=family_id, name="X", occurred_at=_NOW),
            FamilySettingsSchemaUpdated(
                family_id=family_id,
                settings_schema=_TEST_SCHEMA,
                occurred_at=_NOW,
            ),
            FamilyVersioned(family_id=family_id, version_tag="v2", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.version == "v2"
    assert state.settings_schema == _TEST_SCHEMA


@pytest.mark.unit
def test_settings_schema_preserved_across_deprecation() -> None:
    """FamilyDeprecated preserves the settings_schema for audit reconstruction.

    Same independence as the version arm: audit needs to answer
    'what shape did this capability declare at its last update?'
    """
    family_id = uuid4()
    state = fold(
        [
            FamilyDefined(family_id=family_id, name="X", occurred_at=_NOW),
            FamilySettingsSchemaUpdated(
                family_id=family_id,
                settings_schema=_TEST_SCHEMA,
                occurred_at=_NOW,
            ),
            FamilyDeprecated(reason="Superseded", family_id=family_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is FamilyStatus.DEPRECATED
    assert state.settings_schema == _TEST_SCHEMA


@pytest.mark.unit
def test_capability_settings_schema_updated_on_empty_state_raises() -> None:
    """Like all transition events, schema-update before genesis is
    stream corruption."""
    family_id = uuid4()
    with pytest.raises(ValueError, match="empty state"):
        fold(
            [
                FamilySettingsSchemaUpdated(
                    family_id=family_id,
                    settings_schema=_TEST_SCHEMA,
                    occurred_at=_NOW,
                ),
            ]
        )


# ---------- affordance folding semantics ----------
#
# Gate review P0 (test coverage): the original 5j commit had ZERO
# tests asserting `state.affordances` for any non-empty value. These
# tests pin the 4 evolver arms' affordance semantics:
#   - FamilyDefined → state.affordances = event.affordances (genesis)
#   - FamilyVersioned → state.affordances = event.affordances (REPLACES)
#   - FamilyDeprecated → state.affordances PRESERVED
#   - FamilySettingsSchemaUpdated → state.affordances PRESERVED


@pytest.mark.unit
def test_family_defined_folds_non_empty_affordances() -> None:
    family_id = uuid4()
    event = FamilyDefined(
        family_id=family_id,
        name="RotaryStage",
        occurred_at=_NOW,
        affordances=frozenset({Affordance.ROTATABLE, Affordance.HOMEABLE}),
    )
    state = evolve(None, event)
    assert state.affordances == frozenset({Affordance.ROTATABLE, Affordance.HOMEABLE})


@pytest.mark.unit
def test_family_versioned_replaces_affordances_wholesale() -> None:
    """Replace-on-version semantics: a new version IS a new
    declaration. Versioning with `{Homeable}` over a prior `{Rotatable}`
    yields `{Homeable}` only, NOT the merged union."""
    family_id = uuid4()
    initial = evolve(
        None,
        FamilyDefined(
            family_id=family_id,
            name="X",
            occurred_at=_NOW,
            affordances=frozenset({Affordance.ROTATABLE}),
        ),
    )
    versioned = evolve(
        initial,
        FamilyVersioned(
            family_id=family_id,
            version_tag="v2",
            occurred_at=_NOW,
            affordances=frozenset({Affordance.HOMEABLE}),
        ),
    )
    assert versioned.affordances == frozenset({Affordance.HOMEABLE})


@pytest.mark.unit
def test_family_deprecated_preserves_affordances() -> None:
    """Affordances stay in state across deprecation — audit-critical:
    operators reading a deprecated Family must still see what it
    declared at its last version."""
    family_id = uuid4()
    initial = evolve(
        None,
        FamilyDefined(
            family_id=family_id,
            name="X",
            occurred_at=_NOW,
            affordances=frozenset({Affordance.ROTATABLE, Affordance.HOMEABLE}),
        ),
    )
    deprecated = evolve(
        initial,
        FamilyDeprecated(reason="Superseded", family_id=family_id, occurred_at=_NOW),
    )
    assert deprecated.affordances == frozenset({Affordance.ROTATABLE, Affordance.HOMEABLE})


@pytest.mark.unit
def test_family_settings_schema_updated_preserves_affordances() -> None:
    """Affordances and settings_schema evolve independently. Updating
    one does not affect the other."""
    family_id = uuid4()
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}
    initial = evolve(
        None,
        FamilyDefined(
            family_id=family_id,
            name="X",
            occurred_at=_NOW,
            affordances=frozenset({Affordance.ROTATABLE}),
        ),
    )
    with_schema = evolve(
        initial,
        FamilySettingsSchemaUpdated(
            family_id=family_id,
            settings_schema=schema,
            occurred_at=_NOW,
        ),
    )
    assert with_schema.affordances == frozenset({Affordance.ROTATABLE})
    assert with_schema.settings_schema == schema
