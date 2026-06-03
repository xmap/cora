"""Property-based test for the AssetOwner identifier-pairing invariant.

Section 9.6 of the design memo. Pins the both-set-or-both-None
invariant universally across generated inputs; subsumes the two
example-based negative tests in `test_asset_owner_vo.py` (kept as
readable examples per the standard Hypothesis-plus-examples
pattern).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    ASSET_OWNER_IDENTIFIER_MAX_LENGTH,
    ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH,
    ASSET_OWNER_NAME_MAX_LENGTH,
    AssetOwner,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
    InvalidAssetOwnerIdentifierPairingError,
)

_PRINTABLE = st.characters(min_codepoint=0x21, max_codepoint=0x7E)
_NAME_STR = st.text(alphabet=_PRINTABLE, min_size=1, max_size=ASSET_OWNER_NAME_MAX_LENGTH)
_ID_STR = st.text(alphabet=_PRINTABLE, min_size=1, max_size=ASSET_OWNER_IDENTIFIER_MAX_LENGTH)
_TYPE_STR = st.text(
    alphabet=_PRINTABLE, min_size=1, max_size=ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH
)


@pytest.mark.unit
@given(
    name=_NAME_STR,
    identifier=st.one_of(st.none(), _ID_STR),
    identifier_type=st.one_of(st.none(), _TYPE_STR),
)
def test_asset_owner_pairing_invariant_iff_both_set_or_both_none_holds(
    name: str,
    identifier: str | None,
    identifier_type: str | None,
) -> None:
    """For arbitrary (identifier, identifier_type) None/non-None patterns,
    AssetOwner construction raises `InvalidAssetOwnerIdentifierPairingError`
    iff exactly one of the two is None (XOR)."""
    name_vo = AssetOwnerName(name)
    id_vo = AssetOwnerIdentifier(identifier) if identifier is not None else None
    type_vo = AssetOwnerIdentifierType(identifier_type) if identifier_type is not None else None

    pairing_violated = (id_vo is None) != (type_vo is None)

    if pairing_violated:
        with pytest.raises(InvalidAssetOwnerIdentifierPairingError):
            AssetOwner(
                name=name_vo,
                identifier=id_vo,
                identifier_type=type_vo,
            )
    else:
        owner = AssetOwner(
            name=name_vo,
            identifier=id_vo,
            identifier_type=type_vo,
        )
        assert owner.identifier == id_vo
        assert owner.identifier_type == type_vo
