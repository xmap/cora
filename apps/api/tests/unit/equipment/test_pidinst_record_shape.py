"""Construction-time invariant tests for the `PidinstRecord` intermediate.

Section 7.4 of the design memo. These tests exercise the dataclass
`__post_init__` directly without going through the serializer, to
confirm the intermediate is self-validating. Every backstop invariant
listed in section 6.7 of the design memo gets a dedicated test that
asserts `PidinstRecordInvariantError` is raised explicitly via
if-raise rather than via bare `assert` (which `python -O` would strip).
"""

from dataclasses import replace

import pytest

from cora.equipment._pidinst_types import (
    Manufacturer,
    Owner,
    PidinstAlternateIdentifier,
    PidinstDate,
    PidinstIdentifier,
    PidinstIdentifierType,
    PidinstModel,
    PidinstRecord,
    SchemaVersion,
)
from cora.equipment.errors import PidinstRecordInvariantError

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]


def _record(**overrides: object) -> PidinstRecord:
    base = PidinstRecord(
        identifier=PidinstIdentifier(
            value="urn:uuid:01900000-0000-7000-8000-00000000d001",
            scheme=PidinstIdentifierType.URN,
        ),
        schema_version=SchemaVersion.V1_0,
        landing_page="https://cora.example/assets/x",
        name="Rotary Stage A",
        publisher="Argonne National Laboratory",
        publication_year=2024,
        owners=(Owner(name="Advanced Photon Source"),),
        manufacturers=(Manufacturer(name="Aerotech"),),
        model=PidinstModel(name="ANT130-L", identifier="ANT130-L-RM"),
        description=None,
        instrument_types=(),
        measured_variables=(),
        dates=(),
        related_identifiers=(),
        alternate_identifiers=(),
        measurement_techniques=(),
    )
    return replace(base, **overrides) if overrides else base


def test_pidinst_record_with_zero_manufacturers_raises_invariant_error() -> None:
    with pytest.raises(PidinstRecordInvariantError):
        _record(manufacturers=())


def test_pidinst_record_with_invalid_date_type_raises_invariant_error() -> None:
    # Construct a PidinstDate with a fake string date_type to bypass the
    # outer dataclass's StrEnum typing and exercise the record's
    # __post_init__ membership check directly.
    bad_date = PidinstDate.__new__(PidinstDate)
    object.__setattr__(bad_date, "value", "2024-01-01")
    object.__setattr__(bad_date, "date_type", "NotARealDateType")
    with pytest.raises(PidinstRecordInvariantError):
        _record(dates=(bad_date,))


def test_pidinst_record_with_invalid_alternate_identifier_kind_raises_invariant_error() -> None:
    bad_alt = PidinstAlternateIdentifier.__new__(PidinstAlternateIdentifier)
    object.__setattr__(bad_alt, "value", "SN-1")
    object.__setattr__(bad_alt, "kind", "SerialNumber")  # string, not enum
    object.__setattr__(bad_alt, "name", None)
    with pytest.raises(PidinstRecordInvariantError):
        _record(alternate_identifiers=(bad_alt,))


def test_pidinst_record_with_empty_identifier_raises_invariant_error() -> None:
    with pytest.raises(PidinstRecordInvariantError):
        _record(identifier=PidinstIdentifier(value="", scheme=PidinstIdentifierType.URN))


def test_pidinst_record_with_empty_landing_page_raises_invariant_error() -> None:
    with pytest.raises(PidinstRecordInvariantError):
        _record(landing_page="")


def test_pidinst_record_with_empty_name_raises_invariant_error() -> None:
    with pytest.raises(PidinstRecordInvariantError):
        _record(name="")


def test_pidinst_record_with_owner_identifier_without_type_raises_invariant_error() -> None:
    # The Owner VO's own __post_init__ catches this first; either point
    # raising PidinstRecordInvariantError is acceptable per L8 (same
    # error class for both the VO check and the record check).
    with pytest.raises(PidinstRecordInvariantError):
        Owner(name="ANL", identifier="https://ror.org/05gvnxz63", identifier_type=None)


def test_pidinst_record_owner_identifier_type_only_raises_invariant_error() -> None:
    with pytest.raises(PidinstRecordInvariantError):
        Owner(name="ANL", identifier=None, identifier_type="ROR")


def test_pidinst_record_schema_version_pinned_to_v1_0() -> None:
    record = _record()
    assert record.schema_version is SchemaVersion.V1_0
    assert SchemaVersion.V1_0.value == "1.0"
