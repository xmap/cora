"""Family stream-id derivation: deterministic UUID5 over a fixed namespace."""

import unicodedata
from uuid import UUID, uuid5

import pytest

from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.role import RoleName, role_stream_id

# Expected namespace UUID locked in `_family_registry.py`. The literal
# lives here as a regression guard against silent drift; the private
# constant MUST stay byte-identical to this value or every existing
# Family stream becomes unreachable.
_EXPECTED_FAMILY_NAMESPACE = UUID("14ce275b-7d45-54b0-887e-972a88c69d98")

# 'e' followed by the combining acute accent (U+0301): a decomposed
# spelling that renders as 'e-acute' but is a different code-point
# sequence from the precomposed single character (U+00E9). Built with
# chr() so the source stays pure ASCII and the two forms cannot be
# silently folded together by an editor.
_COMBINING_ACUTE = chr(0x0301)


@pytest.mark.unit
def test_family_stream_id_is_deterministic_for_same_name() -> None:
    a = family_stream_id(FamilyName("Camera"))
    b = family_stream_id(FamilyName("Camera"))
    assert a == b


@pytest.mark.unit
def test_family_stream_id_is_case_insensitive() -> None:
    assert family_stream_id(FamilyName("Camera")) == family_stream_id(FamilyName("camera"))


@pytest.mark.unit
def test_family_stream_id_differs_for_different_names() -> None:
    assert family_stream_id(FamilyName("Camera")) != family_stream_id(FamilyName("Objective"))


@pytest.mark.unit
def test_family_stream_id_matches_uuid5_namespace_derivation() -> None:
    """Regression guard: the namespace UUID is load-bearing for stream
    continuity. Changing it would orphan every existing Family stream.
    The derivation NFC-normalizes then lower-cases the name before uuid5."""
    assert family_stream_id(FamilyName("Tomography")) == uuid5(
        _EXPECTED_FAMILY_NAMESPACE, "tomography"
    )


@pytest.mark.unit
def test_family_stream_id_is_nfc_normalized() -> None:
    """Composed vs decomposed Unicode for the same name converge on one
    stream id, so a federation-shared Family name cannot fork on a
    spelling that renders identically."""
    decomposed = "Cafe" + _COMBINING_ACUTE + "Probe"
    composed = unicodedata.normalize("NFC", decomposed)
    assert decomposed != composed
    assert family_stream_id(FamilyName(decomposed)) == family_stream_id(FamilyName(composed))


@pytest.mark.unit
def test_role_stream_id_is_nfc_normalized() -> None:
    decomposed = "Cafe" + _COMBINING_ACUTE + "Role"
    composed = unicodedata.normalize("NFC", decomposed)
    assert decomposed != composed
    assert role_stream_id(RoleName(decomposed)) == role_stream_id(RoleName(composed))


@pytest.mark.unit
def test_family_stream_id_does_not_alias_role_stream_id() -> None:
    """Cross-aggregate safety: a Family and a Role with the same name
    must derive to distinct stream ids (distinct namespace sentinels)."""
    assert family_stream_id(FamilyName("Imager")) != role_stream_id(RoleName("Imager"))
