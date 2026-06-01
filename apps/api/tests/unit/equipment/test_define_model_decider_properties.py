"""Property-based tests for `define_model.decide` (Equipment BC).

Mirrors the Recipe BC `define_capability` decider-PBT pattern on an
Equipment BC create-style command with bounded-text VOs, an optional
paired manufacturer identifier, and a non-empty `declared_families`
frozenset invariant. Universal claims across generated inputs:

  - state=None + valid command emits a single ModelDefined with the
    injected new_id / now and the command's manufacturer / parts /
    declared_families intact.
  - state=Model always raises ModelAlreadyExistsError, carrying the
    pre-existing model_id.
  - Empty `declared_families` always raises InvalidDeclaredFamiliesError.
  - Empty, whitespace-only, or over-long `name` always raises
    InvalidModelNameError (via the ModelName VO).
  - Empty, whitespace-only, or over-long `part_number` always raises
    InvalidPartNumberError (via the PartNumber VO).
  - Empty, whitespace-only, or over-long `version_tag` (when non-None)
    always raises InvalidModelVersionTagError (via the ModelVersionTag
    VO).
  - Pure: same (state, command, now, new_id) returns the same events.
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
    ModelAlreadyExistsError,
    ModelDefined,
    ModelName,
    PartNumber,
)
from cora.equipment.features import define_model
from cora.equipment.features.define_model import DefineModel
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

# Negative-case alphabet for bounded-text VOs: empty, whitespace-only,
# and over-long strings. Each ALWAYS raises after `.strip()` either
# yields "" (empty/whitespace) or exceeds the length cap.
_WHITESPACE_CHARS = st.sampled_from([" ", "\t", "\n", "\r", "  ", " \t\n"])


def _invalid_bounded_text(max_length: int) -> st.SearchStrategy[str]:
    """Empty, whitespace-only, or over-length strings for VO rejection PBTs.

    Bounded-text VOs reject when `.strip()` yields an empty string or
    when the trimmed length exceeds `max_length`. This strategy unions
    all three rejection shapes; every drawn value triggers the VO's
    error class.
    """
    return st.one_of(
        st.just(""),
        _WHITESPACE_CHARS,
        printable_ascii_text(min_size=max_length + 1, max_size=max_length + 50),
    )


@st.composite
def _manufacturers(draw: st.DrawFn) -> Manufacturer:
    """Build a Manufacturer VO with optional paired identifier + type.

    The pairing invariant is enforced inside the Manufacturer dataclass:
    `identifier` and `identifier_type` are both set or both None. This
    composite draws both halves together so generated Manufacturers
    always satisfy the invariant.
    """
    name = ManufacturerName(draw(_MANUFACTURER_NAME))
    has_identifier = draw(st.booleans())
    if not has_identifier:
        return Manufacturer(name=name)
    identifier = ManufacturerIdentifier(draw(_MANUFACTURER_IDENTIFIER))
    identifier_type = draw(st.sampled_from(list(ManufacturerIdentifierType)))
    return Manufacturer(name=name, identifier=identifier, identifier_type=identifier_type)


def _command(
    *,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str | None = None,
) -> DefineModel:
    return DefineModel(
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )


def _model(model_id: UUID) -> Model:
    return Model(
        id=model_id,
        name=ModelName("Existing"),
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number=PartNumber("P"),
        declared_families=frozenset({model_id}),
    )


@pytest.mark.unit
@given(
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=st.one_of(st.none(), _VERSION_TAG),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_model_emits_exactly_one_event_with_injected_fields(
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream + valid command -> single ModelDefined with injected ids/time."""
    command = _command(
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    events = define_model.decide(state=None, command=command, now=now, new_id=new_id)
    assert events == [
        ModelDefined(
            model_id=new_id,
            name=name,
            manufacturer=manufacturer,
            part_number=part_number,
            declared_families=declared_families,
            occurred_at=now,
            version_tag=version_tag,
        )
    ]


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=st.one_of(st.none(), _VERSION_TAG),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_model_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state -> ModelAlreadyExistsError, regardless of command."""
    command = _command(
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    with pytest.raises(ModelAlreadyExistsError) as exc:
        define_model.decide(state=_model(existing_id), command=command, now=now, new_id=new_id)
    assert exc.value.model_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    version_tag=st.one_of(st.none(), _VERSION_TAG),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_model_with_empty_declared_families_always_raises(
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    version_tag: str | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty declared_families -> InvalidDeclaredFamiliesError, regardless of other fields."""
    command = _command(
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=frozenset[UUID](),
        version_tag=version_tag,
    )
    with pytest.raises(InvalidDeclaredFamiliesError):
        define_model.decide(state=None, command=command, now=now, new_id=new_id)


@pytest.mark.unit
@given(
    name=_invalid_bounded_text(MODEL_NAME_MAX_LENGTH),
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=st.one_of(st.none(), _VERSION_TAG),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_model_with_invalid_name_always_raises(
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty, whitespace-only, or over-long name -> InvalidModelNameError."""
    command = _command(
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    with pytest.raises(InvalidModelNameError):
        define_model.decide(state=None, command=command, now=now, new_id=new_id)


@pytest.mark.unit
@given(
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_invalid_bounded_text(MODEL_PART_NUMBER_MAX_LENGTH),
    declared_families=_DECLARED_FAMILIES,
    version_tag=st.one_of(st.none(), _VERSION_TAG),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_model_with_invalid_part_number_always_raises(
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty, whitespace-only, or over-long part_number -> InvalidPartNumberError."""
    command = _command(
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    with pytest.raises(InvalidPartNumberError):
        define_model.decide(state=None, command=command, now=now, new_id=new_id)


@pytest.mark.unit
@given(
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=_invalid_bounded_text(MODEL_VERSION_TAG_MAX_LENGTH),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_model_with_invalid_version_tag_always_raises(
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty, whitespace-only, or over-long non-None version_tag ->
    InvalidModelVersionTagError. None is excluded from this strategy
    because None is a valid version_tag (no initial revision label).
    """
    command = _command(
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    with pytest.raises(InvalidModelVersionTagError):
        define_model.decide(state=None, command=command, now=now, new_id=new_id)


@pytest.mark.unit
@given(
    name=_NAME,
    manufacturer=_manufacturers(),
    part_number=_PART_NUMBER,
    declared_families=_DECLARED_FAMILIES,
    version_tag=st.one_of(st.none(), _VERSION_TAG),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_model_is_pure_same_input_same_output(
    name: str,
    manufacturer: Manufacturer,
    part_number: str,
    declared_families: frozenset[UUID],
    version_tag: str | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    command = _command(
        name=name,
        manufacturer=manufacturer,
        part_number=part_number,
        declared_families=declared_families,
        version_tag=version_tag,
    )
    first = define_model.decide(state=None, command=command, now=now, new_id=new_id)
    second = define_model.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
