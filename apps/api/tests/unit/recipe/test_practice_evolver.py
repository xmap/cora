"""Unit tests for the Practice aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.practice import (
    Practice,
    PracticeName,
    PracticeStatus,
    evolve,
    fold,
)
from cora.recipe.aggregates.practice.events import (
    PracticeDefined,
    PracticeDeprecated,
    PracticeVersioned,
)
from cora.recipe.features import define_practice
from cora.recipe.features.define_practice import DefinePractice

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_practice_defined_sets_status_to_defined() -> None:
    """PracticeDefined is the genesis event; status defaults to
    Defined via the evolver. version starts None."""
    practice_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    state = evolve(
        None,
        PracticeDefined(
            practice_id=practice_id,
            name="APS Standard Tomography",
            method_id=method_id,
            site_id=site_id,
            occurred_at=_NOW,
        ),
    )
    assert state == Practice(
        id=practice_id,
        name=PracticeName("APS Standard Tomography"),
        method_id=method_id,
        site_id=site_id,
        status=PracticeStatus.DEFINED,
    )
    assert state.version is None


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_practice_defined_returns_practice() -> None:
    practice_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    state = fold(
        [
            PracticeDefined(
                practice_id=practice_id,
                name="APS Sector 2 XRF",
                method_id=method_id,
                site_id=site_id,
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Practice(
        id=practice_id,
        name=PracticeName("APS Sector 2 XRF"),
        method_id=method_id,
        site_id=site_id,
        status=PracticeStatus.DEFINED,
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    practice_id = uuid4()
    events = [
        PracticeDefined(
            practice_id=practice_id,
            name="X",
            method_id=uuid4(),
            site_id=uuid4(),
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """End-to-end: decider produces events that the evolver folds back."""
    new_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    command = DefinePractice(
        name="  APS Standard Tomography  ",  # whitespace exercises VO trim
        method_id=method_id,
        site_id=site_id,
    )
    events = define_practice.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)
    assert rebuilt == Practice(
        id=new_id,
        name=PracticeName("APS Standard Tomography"),
        method_id=method_id,
        site_id=site_id,
        status=PracticeStatus.DEFINED,
    )


# ---------- PracticeVersioned ----------


@pytest.mark.unit
def test_evolve_practice_versioned_flips_status_and_sets_version() -> None:
    practice_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    defined = Practice(
        id=practice_id,
        name=PracticeName("APS Standard Tomography"),
        method_id=method_id,
        site_id=site_id,
        status=PracticeStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        PracticeVersioned(practice_id=practice_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.status is PracticeStatus.VERSIONED
    assert versioned.version == "v2"
    # Cross-aggregate refs preserved.
    assert versioned.method_id == method_id
    assert versioned.site_id == site_id
    assert versioned.id == practice_id


@pytest.mark.unit
def test_evolve_practice_versioned_replaces_prior_version_tag() -> None:
    practice_id = uuid4()
    versioned_v1 = Practice(
        id=practice_id,
        name=PracticeName("X"),
        method_id=uuid4(),
        site_id=uuid4(),
        status=PracticeStatus.VERSIONED,
        version="v1",
    )
    versioned_v2 = evolve(
        versioned_v1,
        PracticeVersioned(practice_id=practice_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned_v2.version == "v2"


@pytest.mark.unit
def test_evolve_practice_versioned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            PracticeVersioned(practice_id=uuid4(), version_tag="v1", occurred_at=_NOW),
        )


# ---------- PracticeDeprecated ----------


@pytest.mark.unit
def test_evolve_practice_deprecated_flips_status_and_preserves_version() -> None:
    """Version preserved across deprecation. Mirrors Method
    and Family shape."""
    practice_id = uuid4()
    method_id = uuid4()
    site_id = uuid4()
    versioned = Practice(
        id=practice_id,
        name=PracticeName("X"),
        method_id=method_id,
        site_id=site_id,
        status=PracticeStatus.VERSIONED,
        version="v3",
    )
    deprecated = evolve(
        versioned,
        PracticeDeprecated(reason="Superseded", practice_id=practice_id, occurred_at=_NOW),
    )
    assert deprecated.status is PracticeStatus.DEPRECATED
    assert deprecated.version == "v3"
    # Cross-aggregate refs preserved across deprecation.
    assert deprecated.method_id == method_id
    assert deprecated.site_id == site_id


@pytest.mark.unit
def test_evolve_practice_deprecated_from_defined_preserves_null_version() -> None:
    defined = Practice(
        id=uuid4(),
        name=PracticeName("X"),
        method_id=uuid4(),
        site_id=uuid4(),
        status=PracticeStatus.DEFINED,
    )
    deprecated = evolve(
        defined,
        PracticeDeprecated(reason="Superseded", practice_id=defined.id, occurred_at=_NOW),
    )
    assert deprecated.status is PracticeStatus.DEPRECATED
    assert deprecated.version is None


@pytest.mark.unit
def test_evolve_practice_deprecated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, PracticeDeprecated(reason="Superseded", practice_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_define_version_yields_versioned_practice() -> None:
    practice_id = uuid4()
    state = fold(
        [
            PracticeDefined(
                practice_id=practice_id,
                name="X",
                method_id=uuid4(),
                site_id=uuid4(),
                occurred_at=_NOW,
            ),
            PracticeVersioned(practice_id=practice_id, version_tag="v2", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is PracticeStatus.VERSIONED
    assert state.version == "v2"


@pytest.mark.unit
def test_fold_define_version_deprecate_preserves_version() -> None:
    """Full lifecycle audit: define → version → deprecate keeps the
    last version_tag as a historical record on the deprecated state."""
    practice_id = uuid4()
    state = fold(
        [
            PracticeDefined(
                practice_id=practice_id,
                name="X",
                method_id=uuid4(),
                site_id=uuid4(),
                occurred_at=_NOW,
            ),
            PracticeVersioned(practice_id=practice_id, version_tag="v2", occurred_at=_NOW),
            PracticeDeprecated(reason="Superseded", practice_id=practice_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is PracticeStatus.DEPRECATED
    assert state.version == "v2"


@pytest.mark.unit
def test_evolve_practice_versioned_preserves_method_and_site_refs() -> None:
    """Critical pin: method_id and site_id MUST carry through the
    version transition. Same safety-net pattern as Method's evolver
    preserve tests."""
    method_id = uuid4()
    site_id = uuid4()
    defined = Practice(
        id=uuid4(),
        name=PracticeName("X"),
        method_id=method_id,
        site_id=site_id,
        status=PracticeStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        PracticeVersioned(practice_id=defined.id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.method_id == method_id
    assert versioned.site_id == site_id
