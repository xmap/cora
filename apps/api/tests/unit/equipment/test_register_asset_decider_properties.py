"""Property-based tests for `register_asset.decide` (Equipment BC).

Universal claims across generated inputs, scoped to the model_id
propagation contract added by the asset-model-binding slice and
to the alternate_identifiers propagation contract added by the
asset-alternate-identifiers slice:

  - state=None + valid command + any `model_id` (UUID-or-None)
    emits a single `AssetRegistered` whose `model_id` field equals
    the command's `model_id` verbatim. The decider does NOT load
    the Model snapshot per Lock B; the handler is the seam that
    enforces existence.
  - state=None + valid command + any `alternate_identifiers`
    frozenset emits a single `AssetRegistered` whose
    `alternate_identifiers` field equals the command's set
    verbatim. The decider does NOT cross-validate (kind, value)
    uniqueness across Assets in v1 per Lock F.
  - Pure: same (state, command, now, new_id) returns the same
    events for any model_id + alternate_identifiers choice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    AssetLevel,
    AssetRegistered,
)
from cora.equipment.features import register_asset
from cora.equipment.features.register_asset import RegisterAsset
from cora.shared.identifier import (
    ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
    AlternateIdentifier,
    AlternateIdentifierKind,
)
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))


if TYPE_CHECKING:
    from datetime import datetime


_NAME = printable_ascii_text(min_size=1, max_size=200)
_NON_ENTERPRISE_LEVELS = st.sampled_from(
    [
        AssetLevel.SITE,
        AssetLevel.AREA,
        AssetLevel.UNIT,
        AssetLevel.COMPONENT,
        AssetLevel.DEVICE,
    ]
)
_ALTERNATE_IDENTIFIER_KINDS = st.sampled_from(list(AlternateIdentifierKind))
_ALTERNATE_IDENTIFIER_VALUES = printable_ascii_text(
    min_size=1, max_size=ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH
)
_ALTERNATE_IDENTIFIERS = st.frozensets(
    st.builds(
        AlternateIdentifier,
        kind=_ALTERNATE_IDENTIFIER_KINDS,
        value=_ALTERNATE_IDENTIFIER_VALUES,
    ),
    max_size=5,
)


@pytest.mark.unit
@given(
    name=_NAME,
    level=_NON_ENTERPRISE_LEVELS,
    parent_id=st.uuids(),
    model_id=st.one_of(st.none(), st.uuids()),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_asset_propagates_model_id_verbatim_into_event(
    name: str,
    level: AssetLevel,
    parent_id: UUID,
    model_id: UUID | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any (UUID-or-None) `model_id` on the command rides AssetRegistered
    unchanged. The decider does not inspect or load the referenced Model
    stream; that is the handler's responsibility per Lock B."""
    command = RegisterAsset(
        name=name,
        level=level,
        parent_id=parent_id,
        model_id=model_id,
    )
    events = register_asset.decide(
        state=None, command=command, now=now, new_id=new_id, commissioned_by=_TEST_ACTOR_ID
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssetRegistered)
    assert event.model_id == model_id


@pytest.mark.unit
@given(
    name=_NAME,
    level=_NON_ENTERPRISE_LEVELS,
    parent_id=st.uuids(),
    model_id=st.one_of(st.none(), st.uuids()),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_asset_is_pure_across_model_id_inputs(
    name: str,
    level: AssetLevel,
    parent_id: UUID,
    model_id: UUID | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args (including model_id) return identical
    events. Pins decider purity over the new model_id axis."""
    command = RegisterAsset(
        name=name,
        level=level,
        parent_id=parent_id,
        model_id=model_id,
    )
    first = register_asset.decide(
        state=None, command=command, now=now, new_id=new_id, commissioned_by=_TEST_ACTOR_ID
    )
    second = register_asset.decide(
        state=None, command=command, now=now, new_id=new_id, commissioned_by=_TEST_ACTOR_ID
    )
    assert first == second


@pytest.mark.unit
@given(
    name=_NAME,
    level=_NON_ENTERPRISE_LEVELS,
    parent_id=st.uuids(),
    alternate_identifiers=_ALTERNATE_IDENTIFIERS,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_asset_propagates_alternate_identifiers_verbatim_into_event(
    name: str,
    level: AssetLevel,
    parent_id: UUID,
    alternate_identifiers: frozenset[AlternateIdentifier],
    now: datetime,
    new_id: UUID,
) -> None:
    """Any frozenset[AlternateIdentifier] on the command rides
    AssetRegistered unchanged. The decider does not cross-validate
    (kind, value) uniqueness across Assets per Lock F; frozenset
    semantics on the command structurally forbid in-Asset duplicates."""
    command = RegisterAsset(
        name=name,
        level=level,
        parent_id=parent_id,
        alternate_identifiers=alternate_identifiers,
    )
    events = register_asset.decide(
        state=None, command=command, now=now, new_id=new_id, commissioned_by=_TEST_ACTOR_ID
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssetRegistered)
    assert event.alternate_identifiers == alternate_identifiers


@pytest.mark.unit
@given(
    name=_NAME,
    level=_NON_ENTERPRISE_LEVELS,
    parent_id=st.uuids(),
    alternate_identifiers=_ALTERNATE_IDENTIFIERS,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_asset_is_pure_across_alternate_identifiers_inputs(
    name: str,
    level: AssetLevel,
    parent_id: UUID,
    alternate_identifiers: frozenset[AlternateIdentifier],
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args (including alternate_identifiers)
    return identical events. Pins decider purity over the new
    alternate_identifiers axis."""
    command = RegisterAsset(
        name=name,
        level=level,
        parent_id=parent_id,
        alternate_identifiers=alternate_identifiers,
    )
    first = register_asset.decide(
        state=None, command=command, now=now, new_id=new_id, commissioned_by=_TEST_ACTOR_ID
    )
    second = register_asset.decide(
        state=None, command=command, now=now, new_id=new_id, commissioned_by=_TEST_ACTOR_ID
    )
    assert first == second
