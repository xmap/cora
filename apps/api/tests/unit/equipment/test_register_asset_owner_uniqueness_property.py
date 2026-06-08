"""Property-based test: register_asset rejects payloads whose owners
share a name (Lock 6).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    ASSET_OWNER_CONTACT_MAX_LENGTH,
    ASSET_OWNER_NAME_MAX_LENGTH,
    AssetLevel,
    AssetOwner,
    AssetOwnerAlreadyPresentError,
    AssetOwnerContact,
    AssetOwnerName,
)
from cora.equipment.features.register_asset.command import RegisterAsset
from cora.equipment.features.register_asset.decider import decide as register_decide
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))


_PRINTABLE = st.characters(min_codepoint=0x21, max_codepoint=0x7E)
_NAME_STR = st.text(alphabet=_PRINTABLE, min_size=1, max_size=ASSET_OWNER_NAME_MAX_LENGTH)
_CONTACT_STR = st.text(alphabet=_PRINTABLE, min_size=1, max_size=ASSET_OWNER_CONTACT_MAX_LENGTH)
_NOW = datetime(2026, 6, 3, 0, 0, 0, tzinfo=UTC)


@st.composite
def _owner_list(draw: st.DrawFn) -> list[AssetOwner]:
    """Draw a list of AssetOwner VOs whose names may or may not
    collide and whose optional contact field differs so the frozenset
    layer does not silently dedupe duplicates."""
    name_pool = draw(st.lists(_NAME_STR.map(AssetOwnerName), min_size=1, max_size=5))
    return [
        AssetOwner(
            name=name,
            contact=AssetOwnerContact(draw(_CONTACT_STR)),
        )
        for name in name_pool
    ]


@pytest.mark.unit
@given(owners=_owner_list())
def test_register_asset_rejects_payload_with_any_duplicate_owner_name_holds(
    owners: list[AssetOwner],
) -> None:
    """The decider raises `AssetOwnerAlreadyPresentError` iff the
    payload contains at least one duplicate name. Each owner here has
    a uniquely-drawn `contact` so distinct-VO frozenset semantics
    cannot mask the test."""
    names = [owner.name.value for owner in owners]
    has_duplicate = len(set(names)) < len(names)
    owner_set = frozenset(owners)
    # If two owners happened to be drawn with identical name AND
    # identical contact, the frozenset deduplicates them and the
    # duplicate-name signal disappears; recompute on the deduped set.
    deduped_names = [owner.name.value for owner in owner_set]
    has_duplicate = len(set(deduped_names)) < len(deduped_names)

    command = RegisterAsset(
        name="X",
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        owners=owner_set,
    )
    if has_duplicate:
        with pytest.raises(AssetOwnerAlreadyPresentError):
            register_decide(
                state=None,
                command=command,
                now=_NOW,
                new_id=uuid4(),
                commissioned_by=_TEST_ACTOR_ID,
            )
    else:
        events = register_decide(
            state=None, command=command, now=_NOW, new_id=uuid4(), commissioned_by=_TEST_ACTOR_ID
        )
        assert events[0].owners == owner_set
