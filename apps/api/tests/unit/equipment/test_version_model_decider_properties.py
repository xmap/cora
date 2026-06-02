"""Property-based tests for `version_model.decide` (Equipment BC).

Mirrors the `define_model` decider-PBT pattern, adapted for the
multi-source `Defined | Versioned -> Versioned` transition. Universal
claims across generated inputs:

  - state in {Defined, Versioned} + valid command emits exactly one
    ModelVersioned with the wholesale replacement payload and the
    injected `now` timestamp.
  - state=None always raises ModelNotFoundError, regardless of command.
  - state.status==Deprecated always raises ModelCannotVersionError.
  - Empty `declared_families` always raises InvalidDeclaredFamiliesError.
  - Empty, whitespace-only, or over-long `name` always raises
    InvalidModelNameError (via the ModelName VO).
  - Empty, whitespace-only, or over-long `part_number` always raises
    InvalidPartNumberError (via the PartNumber VO).
  - Empty, whitespace-only, or over-long `version_tag` always raises
    InvalidModelVersionTagError (via the ModelVersionTag VO). The tag
    is REQUIRED for version_model (unlike define_model).
  - Pure: same (state, command, now) returns the same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.model import (
    MANUFACTURER_IDENTIFIER_MAX_LENGTH,
    MANUFACTURER_NAME_MAX_LENGTH,
    MODEL_NAME_MAX_LENGTH,
    MODEL_PART_NUMBER_MAX_LENGTH,
    MODEL_VERSION_TAG_MAX_LENGTH,
    InvalidDeclaredFamiliesError,
    InvalidModelNameError,
    InvalidModelVersionTagError,
    InvalidPartNumberError,
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
    Model,
    ModelCannotVersionError,
    ModelName,
    ModelNotFoundError,
    ModelStatus,
    ModelVersioned,
    PartNumber,
)
from cora.equipment.features import version_model
from cora.equipment.features.version_model import VersionModel
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime


_NAME = printable_ascii_text(min_size=1, max_size=MODEL_NAME_MAX_LENGTH)
_PART_NUMBER = printable_ascii_text(min_size=1, max_size=MODEL_PART_NUMBER_MAX_LENGTH)
_MANUFACTURER_NAME = printable_ascii_text(min_size=1, max_size=MANUFACTURER_NAME_MAX_LENGTH)
_MANUFACTURER_IDENTIFIER = printable_ascii_text(
    min_size=1, max_size=MANUFACTURER_IDENTIFIER_MAX_LENGTH
)
_VERSION_TAG = printable_ascii_text(min_size=1, max_size=MODEL_VERSION_TAG_MAX_LENGTH)

# 1 to 5 distinct Family ids per the prompt; frozenset dedupes naturally.
_DECLARED_FAMILIES = st.frozensets(st.uuids(), min_size=1, max_size=5)

# Versionable source statuses: Defined (first revision) and Versioned
# (subsequent revisions). Deprecated is excluded; it's covered by a
# dedicated rejection property.
_VERSIONABLE_STATUS = st.sampled_from([ModelStatus.DEFINED, ModelStatus.VERSIONED])

# Negative-case alphabet for bounded-text VOs.
_WHITESPACE_CHARS = st.sampled_from([" ", "\t", "\n", "\r", "  ", " \t\n"])


def _invalid_bounded_text(max_length: int) -> st.SearchStrategy[str]:
    """Empty, whitespace-only, or over-length strings for VO rejection PBTs."""
    return st.one_of(
        st.just(""),
        _WHITESPACE_CHARS,
        printable_ascii_text(min_size=max_length + 1, max_size=max_length + 50),
    )


def _padded_text(inner_strategy: st.SearchStrategy[str]) -> st.SearchStrategy[str]:
    """Wrap an inner text strategy in random leading + trailing whitespace.

    Distinguishes "VO trims at construction" from "decider stores raw
    command text": if the emitted event payload still carries the
    untrimmed wrapper, the decider is leaking `command.<field>` instead
    of the VO's `.value`.
    """

    @st.composite
    def build(draw: st.DrawFn) -> str:
        leading = draw(st.text(alphabet=" \t\n", max_size=10))
        core = draw(inner_strategy)
        trailing = draw(st.text(alphabet=" \t\n", max_size=10))
        return leading + core + trailing

    return build()


@st.composite
def _manufacturers(draw: st.DrawFn) -> Manufacturer:
    """Build a Manufacturer VO with optional paired identifier + type."""
    name = ManufacturerName(draw(_MANUFACTURER_NAME))
    has_identifier = draw(st.booleans())
    if not has_identifier:
        return Manufacturer(name=name)
    identifier = ManufacturerIdentifier(draw(_MANUFACTURER_IDENTIFIER))
    identifier_type = draw(st.sampled_from(list(ManufacturerIdentifierType)))
    return Manufacturer(name=name, identifier=identifier, identifier_type=identifier_type)


def _command(
    *,
    model_id: UUID,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str,
) -> VersionModel:
    return VersionModel(
        model_id=model_id,
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )


def _model(model_id: UUID, *, status: ModelStatus) -> Model:
    return Model(
        id=model_id,
        name=ModelName("Existing"),
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number=PartNumber("P"),
        declared_families=frozenset({model_id}),
        status=status,
        version="v0" if status is ModelStatus.VERSIONED else None,
    )


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_VERSIONABLE_STATUS,
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=_VERSION_TAG,
    now=aware_datetimes(),
)
def test_version_model_emits_exactly_one_event_with_injected_fields(
    model_id: UUID,
    status: ModelStatus,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str,
    now: datetime,
) -> None:
    """Versionable source + valid command -> single ModelVersioned with the
    wholesale-replacement payload and injected `now`."""
    state = _model(model_id, status=status)
    command = _command(
        model_id=model_id,
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    events = version_model.decide(state=state, command=command, now=now)
    assert events == [
        ModelVersioned(
            model_id=model_id,
            name=name,
            manufacturer=manufacturer,
            part_number=part_number,
            declared_families=declared_families,
            version_tag=version_tag,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=_VERSION_TAG,
    now=aware_datetimes(),
)
def test_version_model_on_empty_state_always_raises_not_found(
    model_id: UUID,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str,
    now: datetime,
) -> None:
    """state=None -> ModelNotFoundError carrying command.model_id."""
    command = _command(
        model_id=model_id,
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    with pytest.raises(ModelNotFoundError) as exc:
        version_model.decide(state=None, command=command, now=now)
    assert exc.value.model_id == model_id


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=_VERSION_TAG,
    now=aware_datetimes(),
)
def test_version_model_on_deprecated_state_always_raises_cannot_version(
    model_id: UUID,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str,
    now: datetime,
) -> None:
    """state.status==Deprecated -> ModelCannotVersionError."""
    state = _model(model_id, status=ModelStatus.DEPRECATED)
    command = _command(
        model_id=model_id,
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    with pytest.raises(ModelCannotVersionError) as exc:
        version_model.decide(state=state, command=command, now=now)
    assert exc.value.model_id == model_id
    assert exc.value.current_status is ModelStatus.DEPRECATED


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_VERSIONABLE_STATUS,
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    version_tag=_VERSION_TAG,
    now=aware_datetimes(),
)
def test_version_model_with_empty_declared_families_always_raises(
    model_id: UUID,
    status: ModelStatus,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    version_tag: str,
    now: datetime,
) -> None:
    """Empty declared_families -> InvalidDeclaredFamiliesError, regardless
    of other fields."""
    state = _model(model_id, status=status)
    command = _command(
        model_id=model_id,
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=frozenset[UUID](),
        version_tag=version_tag,
    )
    with pytest.raises(InvalidDeclaredFamiliesError):
        version_model.decide(state=state, command=command, now=now)


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_VERSIONABLE_STATUS,
    name=_invalid_bounded_text(MODEL_NAME_MAX_LENGTH),
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=_VERSION_TAG,
    now=aware_datetimes(),
)
def test_version_model_with_invalid_name_always_raises(
    model_id: UUID,
    status: ModelStatus,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str,
    now: datetime,
) -> None:
    """Empty, whitespace-only, or over-long name -> InvalidModelNameError."""
    state = _model(model_id, status=status)
    command = _command(
        model_id=model_id,
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    with pytest.raises(InvalidModelNameError):
        version_model.decide(state=state, command=command, now=now)


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_VERSIONABLE_STATUS,
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_invalid_bounded_text(MODEL_PART_NUMBER_MAX_LENGTH),
    declared_families=_DECLARED_FAMILIES,
    version_tag=_VERSION_TAG,
    now=aware_datetimes(),
)
def test_version_model_with_invalid_part_number_always_raises(
    model_id: UUID,
    status: ModelStatus,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str,
    now: datetime,
) -> None:
    """Empty, whitespace-only, or over-long part_number -> InvalidPartNumberError."""
    state = _model(model_id, status=status)
    command = _command(
        model_id=model_id,
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    with pytest.raises(InvalidPartNumberError):
        version_model.decide(state=state, command=command, now=now)


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_VERSIONABLE_STATUS,
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=_invalid_bounded_text(MODEL_VERSION_TAG_MAX_LENGTH),
    now=aware_datetimes(),
)
def test_version_model_with_invalid_version_tag_always_raises(
    model_id: UUID,
    status: ModelStatus,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str,
    now: datetime,
) -> None:
    """Empty, whitespace-only, or over-long version_tag -> InvalidModelVersionTagError.
    The tag is REQUIRED here (unlike define_model where None is valid)."""
    state = _model(model_id, status=status)
    command = _command(
        model_id=model_id,
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    with pytest.raises(InvalidModelVersionTagError):
        version_model.decide(state=state, command=command, now=now)


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_VERSIONABLE_STATUS,
    name=_padded_text(_NAME),
    manufacturer=_manufacturers(),
    part_number=_padded_text(_PART_NUMBER),
    declared_families=_DECLARED_FAMILIES,
    version_tag=_padded_text(_VERSION_TAG),
    now=aware_datetimes(),
)
def test_version_model_event_carries_trimmed_name_part_number_and_version_tag(
    model_id: UUID,
    status: ModelStatus,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str,
    now: datetime,
) -> None:
    """Padded input -> ModelVersioned.name / .part_number / .version_tag
    carry the trimmed value, never the raw command string with leading
    or trailing whitespace.

    Closes a coverage gap in printable_ascii_text (which excludes
    whitespace): without this property, the decider could emit raw
    `command.<field>` and still pass every other PBT in this module.
    """
    state = _model(model_id, status=status)
    command = _command(
        model_id=model_id,
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    events = version_model.decide(state=state, command=command, now=now)
    assert len(events) == 1
    event = events[0]
    assert event.name == event.name.strip()
    assert event.part_number == event.part_number.strip()
    assert event.version_tag == event.version_tag.strip()


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_VERSIONABLE_STATUS,
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=_VERSION_TAG,
    now=aware_datetimes(),
)
def test_version_model_is_pure_same_input_same_output(
    model_id: UUID,
    status: ModelStatus,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str,
    now: datetime,
) -> None:
    """Two calls with identical args return identical events."""
    state = _model(model_id, status=status)
    command = _command(
        model_id=model_id,
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    first = version_model.decide(state=state, command=command, now=now)
    second = version_model.decide(state=state, command=command, now=now)
    assert first == second
