"""Property-based tests: add then remove is identity; register then
fold preserves owners set membership.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    ASSET_OWNER_CONTACT_MAX_LENGTH,
    ASSET_OWNER_IDENTIFIER_MAX_LENGTH,
    ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH,
    ASSET_OWNER_NAME_MAX_LENGTH,
    AssetLevel,
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
    evolve,
)
from cora.equipment.aggregates.asset.events import AssetRegistered
from cora.equipment.features import add_asset_owner, remove_asset_owner
from cora.equipment.features.add_asset_owner import AddAssetOwner
from cora.equipment.features.register_asset.command import RegisterAsset
from cora.equipment.features.register_asset.decider import decide as register_decide
from cora.equipment.features.remove_asset_owner import RemoveAssetOwner
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))


_PRINTABLE = st.characters(min_codepoint=0x21, max_codepoint=0x7E)
_NAME = st.text(alphabet=_PRINTABLE, min_size=1, max_size=ASSET_OWNER_NAME_MAX_LENGTH).map(
    AssetOwnerName
)
_CONTACT = st.text(alphabet=_PRINTABLE, min_size=1, max_size=ASSET_OWNER_CONTACT_MAX_LENGTH).map(
    AssetOwnerContact
)
_ID = st.text(alphabet=_PRINTABLE, min_size=1, max_size=ASSET_OWNER_IDENTIFIER_MAX_LENGTH).map(
    AssetOwnerIdentifier
)
_TYPE = st.text(
    alphabet=_PRINTABLE, min_size=1, max_size=ASSET_OWNER_IDENTIFIER_TYPE_MAX_LENGTH
).map(AssetOwnerIdentifierType)
_NOW = datetime(2026, 6, 3, 0, 0, 0, tzinfo=UTC)


@st.composite
def _owner(draw: st.DrawFn) -> AssetOwner:
    name = draw(_NAME)
    contact = draw(st.one_of(st.none(), _CONTACT))
    pair = draw(st.booleans())
    if pair:
        return AssetOwner(
            name=name,
            contact=contact,
            identifier=draw(_ID),
            identifier_type=draw(_TYPE),
        )
    return AssetOwner(name=name, contact=contact)


@pytest.mark.unit
@given(owner=_owner())
def test_add_then_remove_owner_is_identity_holds(owner: AssetOwner) -> None:
    """Register an asset with no owners, add `owner`, remove it by
    name; final state's owners equals the initial empty frozenset."""
    asset_id = uuid4()
    parent_id = uuid4()
    registered_events = register_decide(
        state=None,
        command=RegisterAsset(name="X", level=AssetLevel.UNIT, parent_id=parent_id),
        now=_NOW,
        new_id=asset_id,
        commissioned_by=_TEST_ACTOR_ID,
    )
    state = evolve(None, registered_events[0])

    add_events = add_asset_owner.decide(
        state=state,
        command=AddAssetOwner(asset_id=asset_id, owner=owner),
        now=_NOW,
    )
    state_after_add = evolve(state, add_events[0])
    assert state_after_add.owners == frozenset({owner})

    remove_events = remove_asset_owner.decide(
        state=state_after_add,
        command=RemoveAssetOwner(asset_id=asset_id, owner_name=owner.name),
        now=_NOW,
    )
    state_after_remove = evolve(state_after_add, remove_events[0])
    assert state_after_remove.owners == frozenset()


@pytest.mark.unit
@given(
    owners=st.frozensets(_owner(), min_size=0, max_size=4),
)
def test_register_asset_with_owner_set_then_extract_preserves_set_holds(
    owners: frozenset[AssetOwner],
) -> None:
    """Round-trip through the register decider preserves the set
    membership when the payload has no name collisions. We filter to
    name-distinct owners so the uniqueness guard (Lock 6) does not
    fire."""
    seen: set[AssetOwnerName] = set()
    deduped: set[AssetOwner] = set()
    for owner in owners:
        if owner.name not in seen:
            seen.add(owner.name)
            deduped.add(owner)
    candidate = frozenset(deduped)

    asset_id = uuid4()
    events = register_decide(
        state=None,
        command=RegisterAsset(
            name="X",
            level=AssetLevel.UNIT,
            parent_id=uuid4(),
            owners=candidate,
        ),
        now=_NOW,
        new_id=asset_id,
        commissioned_by=_TEST_ACTOR_ID,
    )
    assert isinstance(events[0], AssetRegistered)
    state = evolve(None, events[0])
    assert state.owners == candidate
