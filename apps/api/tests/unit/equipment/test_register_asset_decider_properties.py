"""Property-based tests for `register_asset.decide` (Equipment BC).

Universal claims across generated inputs, scoped to the model_id
propagation contract added by the asset-model-binding slice:

  - state=None + valid command + any `model_id` (UUID-or-None)
    emits a single `AssetRegistered` whose `model_id` field equals
    the command's `model_id` verbatim. The decider does NOT load
    the Model snapshot per Lock B; the handler is the seam that
    enforces existence.
  - Pure: same (state, command, now, new_id) returns the same
    events for any `model_id` choice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import AssetLevel, AssetRegistered
from cora.equipment.features import register_asset
from cora.equipment.features.register_asset import RegisterAsset
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


_NAME = printable_ascii_text(min_size=1, max_size=200)
_NON_ENTERPRISE_LEVELS = st.sampled_from(
    [
        AssetLevel.SITE,
        AssetLevel.AREA,
        AssetLevel.UNIT,
        AssetLevel.ASSEMBLY,
        AssetLevel.DEVICE,
    ]
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
    events = register_asset.decide(state=None, command=command, now=now, new_id=new_id)
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
    first = register_asset.decide(state=None, command=command, now=now, new_id=new_id)
    second = register_asset.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
