"""Property-based tests for the PersistentIdentifier value object.

Secondary PBT per slice F design memo Section 13.5. Complements the
example-based `test_asset_persistent_id_vo.py` cases with universal
claims over the (scheme, value) input space:

  - For any valid (scheme, value), construction succeeds and the
    scheme round-trips by identity.
  - For any value padded with surrounding whitespace, the canonical
    PersistentIdentifier equals the unpadded version (trim semantics
    of `validate_bounded_text`).
  - For any whitespace-only or empty value, construction raises
    `InvalidPersistentIdentifierValueError` carrying the original
    untrimmed value.
  - For any value whose trimmed length exceeds
    `PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH`, construction raises
    the same error carrying the original untrimmed value.
  - Equal-by-pair PersistentIdentifiers share a hash (frozen
    dataclass set / dict membership).
  - Every member of `PersistentIdentifierScheme` round-trips through
    `.value` lookup (closed-enum integrity).
"""

from __future__ import annotations

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.shared.identifier import (
    PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
    InvalidPersistentIdentifierValueError,
    PersistentIdentifier,
    PersistentIdentifierScheme,
)

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]

_PRINTABLE = st.characters(min_codepoint=0x21, max_codepoint=0x7E)
_VALUE_BODY = st.text(
    alphabet=_PRINTABLE,
    min_size=1,
    max_size=PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
)
_SCHEME = st.sampled_from(list(PersistentIdentifierScheme))
_WS_PAD = st.text(alphabet=" \t\n\r", min_size=1, max_size=5)
_BLANK = st.text(alphabet=" \t\n\r", min_size=0, max_size=10)


@given(scheme=_SCHEME, value=_VALUE_BODY)
def test_persistent_identifier_constructs_for_any_valid_pair(
    scheme: PersistentIdentifierScheme, value: str
) -> None:
    pid = PersistentIdentifier(scheme=scheme, value=value)
    assert pid.scheme is scheme
    assert pid.value == value


@given(scheme=_SCHEME, value=_VALUE_BODY, pad_l=_WS_PAD, pad_r=_WS_PAD)
def test_persistent_identifier_canonicalises_whitespace_padding(
    scheme: PersistentIdentifierScheme,
    value: str,
    pad_l: str,
    pad_r: str,
) -> None:
    assume(value == value.strip())
    padded = PersistentIdentifier(scheme=scheme, value=pad_l + value + pad_r)
    unpadded = PersistentIdentifier(scheme=scheme, value=value)
    assert padded == unpadded
    assert hash(padded) == hash(unpadded)
    assert padded.value == value


@given(scheme=_SCHEME, blank=_BLANK)
def test_persistent_identifier_rejects_blank_value(
    scheme: PersistentIdentifierScheme, blank: str
) -> None:
    with pytest.raises(InvalidPersistentIdentifierValueError) as info:
        PersistentIdentifier(scheme=scheme, value=blank)
    assert info.value.value == blank


@given(
    scheme=_SCHEME,
    overlong=st.text(
        alphabet=_PRINTABLE,
        min_size=PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH + 1,
        max_size=PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH + 50,
    ),
)
def test_persistent_identifier_rejects_overlong_value(
    scheme: PersistentIdentifierScheme, overlong: str
) -> None:
    with pytest.raises(InvalidPersistentIdentifierValueError) as info:
        PersistentIdentifier(scheme=scheme, value=overlong)
    assert info.value.value == overlong


@given(scheme=_SCHEME, value=_VALUE_BODY)
def test_persistent_identifier_equal_pairs_share_hash(
    scheme: PersistentIdentifierScheme, value: str
) -> None:
    first = PersistentIdentifier(scheme=scheme, value=value)
    second = PersistentIdentifier(scheme=scheme, value=value)
    assert first == second
    assert hash(first) == hash(second)
    assert {first, second} == {first}


@given(member=_SCHEME)
def test_persistent_identifier_scheme_value_member_round_trip(
    member: PersistentIdentifierScheme,
) -> None:
    assert PersistentIdentifierScheme(member.value) is member
