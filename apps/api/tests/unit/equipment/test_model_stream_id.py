"""Model stream-id derivation: deterministic UUID5 over the vendor key.

Pins the namespace literal and the canonical-key format (a wrong
literal or a changed join would silently orphan every existing Model
stream), the case rules (manufacturer name folded, part number
preserved), the placeholder fallback, and cross-aggregate non-aliasing.
"""

from uuid import UUID, uuid5

import pytest

from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    PartNumber,
    model_stream_id,
)

# Locked in `_model_registry.py`; mirrored here as a regression guard.
_EXPECTED_MODEL_NAMESPACE = UUID("80ac1aef-8d97-54e2-ae52-22b33b29b3a8")

_UNUSED = UUID(int=0)


def _model(manufacturer: str, part_number: str, *, new_id: UUID = _UNUSED) -> UUID:
    return model_stream_id(
        Manufacturer(name=ManufacturerName(manufacturer)),
        PartNumber(part_number),
        new_id=new_id,
    )


@pytest.mark.unit
def test_model_stream_id_is_deterministic_for_same_vendor_key() -> None:
    assert _model("Aerotech", "ANT130-L") == _model("Aerotech", "ANT130-L")


@pytest.mark.unit
def test_model_stream_id_differs_for_different_part_numbers() -> None:
    assert _model("Aerotech", "ANT130-L") != _model("Aerotech", "ANT95-L")


@pytest.mark.unit
def test_model_stream_id_is_manufacturer_name_case_insensitive() -> None:
    assert _model("Aerotech", "ANT130-L") == _model("aerotech", "ANT130-L")


@pytest.mark.unit
def test_model_stream_id_is_part_number_case_sensitive() -> None:
    """Vendor SKUs are case-sensitive (RV120CCHL != rv120cchl)."""
    assert _model("Newport", "RV120CCHL") != _model("Newport", "rv120cchl")


@pytest.mark.unit
def test_model_stream_id_matches_uuid5_namespace_and_canonical_key() -> None:
    """Regression guard: pins both the namespace literal and the
    length-prefixed, unit-separated canonical join."""
    expected = uuid5(_EXPECTED_MODEL_NAMESPACE, f"{len('aerotech')}:aerotech\x1fANT130-L")
    assert _model("Aerotech", "ANT130-L") == expected


@pytest.mark.unit
def test_model_stream_id_delimiter_injection_yields_distinct_ids() -> None:
    """The length prefix plus unit separator keep the (mfr, pn) boundary
    injective: ("Aero", "techX") and ("Aerotech", "X") must not collide."""
    assert _model("Aero", "techX") != _model("Aerotech", "X")


@pytest.mark.unit
def test_model_stream_id_placeholder_part_number_falls_back_to_random() -> None:
    """The unknown-pending-confirmation placeholder returns the caller's
    random id so distinct unconfirmed Models stay distinct."""
    a, b = UUID(int=1), UUID(int=2)
    id_a = _model("Aerotech", "unknown-pending-confirmation", new_id=a)
    id_b = _model("Aerotech", "unknown-pending-confirmation", new_id=b)
    assert id_a == a
    assert id_b == b
    assert id_a != id_b


@pytest.mark.unit
def test_model_stream_id_does_not_alias_family_stream_id() -> None:
    assert _model("Camera", "Camera") != family_stream_id(FamilyName("Camera"))
