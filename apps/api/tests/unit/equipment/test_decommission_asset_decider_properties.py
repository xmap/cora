"""Property-based tests for `decommission_asset.decide` (Equipment BC).

Complements the example-based `test_decommission_asset_decider.py` with
universal claims across generated inputs. This is a cross-aggregate
decider: it takes a `DecommissionAssetContext` snapshot alongside state.

    (state, command, *, context, now, decommissioned_by) -> [AssetDecommissioned]

Load-bearing properties:

  - A decommissionable Asset (`{Commissioned, Active, Maintenance}`) with
    no fixture binding and no current mount installation emits exactly one
    `AssetDecommissioned` keyed on `state.id` with `occurred_at=now`.
  - A missing aggregate (`state is None`) always raises `AssetNotFoundError`
    carrying the command's `asset_id`.
  - A non-None `state.fixture_id` always raises `AssetHasFixtureBindingError`
    (fires BEFORE the lifecycle check), carrying state.id and the fixture_id.
  - A non-None `context.currently_installed_at_mount_id` always raises
    `AssetIsInstalledError` (fires BEFORE the lifecycle check), carrying
    state.id and the mount_id.
  - A non-decommissionable lifecycle always raises
    `AssetCannotDecommissionError` carrying the current lifecycle.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotDecommissionError,
    AssetDecommissioned,
    AssetHasFixtureBindingError,
    AssetIsInstalledError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features import decommission_asset
from cora.equipment.features.decommission_asset import (
    DecommissionAsset,
    DecommissionAssetContext,
)
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from datetime import datetime

from tests._strategies import aware_datetimes, printable_ascii_text

_TEST_ACTOR_ID = ActorId(UUID(int=1))

_DECOMMISSIONABLE_SOURCES = (
    AssetLifecycle.COMMISSIONED,
    AssetLifecycle.ACTIVE,
    AssetLifecycle.MAINTENANCE,
)
_DISALLOWED_SOURCES = (AssetLifecycle.DECOMMISSIONED,)

_EMPTY_CONTEXT = DecommissionAssetContext(currently_installed_at_mount_id=None)


def _asset(
    *,
    asset_id: UUID,
    name: str,
    lifecycle: AssetLifecycle,
    fixture_id: UUID | None = None,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName(name),
        tier=AssetTier.UNIT,
        parent_id=UUID(int=2),
        lifecycle=lifecycle,
        fixture_id=fixture_id,
    )


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    name=printable_ascii_text(max_size=32),
    source=st.sampled_from(_DECOMMISSIONABLE_SOURCES),
    now=aware_datetimes(),
)
def test_decommission_asset_decommissionable_source_emits_decommissioned_event(
    asset_id: UUID,
    name: str,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """A valid source lifecycle emits one AssetDecommissioned keyed on state.id at now."""
    state = _asset(asset_id=asset_id, name=name, lifecycle=source)
    events = decommission_asset.decide(
        state=state,
        command=DecommissionAsset(asset_id=asset_id),
        context=_EMPTY_CONTEXT,
        now=now,
        decommissioned_by=_TEST_ACTOR_ID,
    )
    assert events == [
        AssetDecommissioned(asset_id=asset_id, occurred_at=now, decommissioned_by=_TEST_ACTOR_ID)
    ]


@pytest.mark.unit
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_decommission_asset_missing_state_raises_not_found(
    asset_id: UUID,
    now: datetime,
) -> None:
    """A None state raises AssetNotFoundError carrying the command's asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        decommission_asset.decide(
            state=None,
            command=DecommissionAsset(asset_id=asset_id),
            context=_EMPTY_CONTEXT,
            now=now,
            decommissioned_by=_TEST_ACTOR_ID,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    name=printable_ascii_text(max_size=32),
    fixture_id=st.uuids(),
    source=st.sampled_from(_DECOMMISSIONABLE_SOURCES),
    now=aware_datetimes(),
)
def test_decommission_asset_with_fixture_binding_raises_has_fixture_binding(
    asset_id: UUID,
    name: str,
    fixture_id: UUID,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """A non-None fixture_id raises AssetHasFixtureBindingError before the lifecycle check."""
    state = _asset(asset_id=asset_id, name=name, lifecycle=source, fixture_id=fixture_id)
    with pytest.raises(AssetHasFixtureBindingError) as exc:
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=asset_id),
            context=_EMPTY_CONTEXT,
            now=now,
            decommissioned_by=_TEST_ACTOR_ID,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.fixture_id == fixture_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    name=printable_ascii_text(max_size=32),
    mount_id=st.uuids(),
    source=st.sampled_from(_DECOMMISSIONABLE_SOURCES),
    now=aware_datetimes(),
)
def test_decommission_asset_installed_at_mount_raises_is_installed(
    asset_id: UUID,
    name: str,
    mount_id: UUID,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """A non-None context mount_id raises AssetIsInstalledError before the lifecycle check."""
    state = _asset(asset_id=asset_id, name=name, lifecycle=source)
    context = DecommissionAssetContext(currently_installed_at_mount_id=mount_id)
    with pytest.raises(AssetIsInstalledError) as exc:
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=asset_id),
            context=context,
            now=now,
            decommissioned_by=_TEST_ACTOR_ID,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.mount_id == mount_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    name=printable_ascii_text(max_size=32),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_decommission_asset_disallowed_lifecycle_raises_cannot_decommission(
    asset_id: UUID,
    name: str,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """A non-decommissionable lifecycle raises AssetCannotDecommissionError with the lifecycle."""
    state = _asset(asset_id=asset_id, name=name, lifecycle=source)
    with pytest.raises(AssetCannotDecommissionError) as exc:
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=asset_id),
            context=_EMPTY_CONTEXT,
            now=now,
            decommissioned_by=_TEST_ACTOR_ID,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.current_lifecycle is source


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    name=printable_ascii_text(max_size=32),
    fixture_id=st.uuids(),
    mount_id=st.uuids(),
    now=aware_datetimes(),
)
def test_decommission_asset_both_cross_aggregate_guards_raises_fixture_first(
    asset_id: UUID,
    name: str,
    fixture_id: UUID,
    mount_id: UUID,
    now: datetime,
) -> None:
    """When fixture binding and mount installation both apply, fixture-binding fires first."""
    state = _asset(
        asset_id=asset_id, name=name, lifecycle=AssetLifecycle.ACTIVE, fixture_id=fixture_id
    )
    context = DecommissionAssetContext(currently_installed_at_mount_id=mount_id)
    with pytest.raises(AssetHasFixtureBindingError):
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=asset_id),
            context=context,
            now=now,
            decommissioned_by=_TEST_ACTOR_ID,
        )


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    name=printable_ascii_text(max_size=32),
    fixture_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_decommission_asset_cross_aggregate_guard_raises_before_lifecycle_guard(
    asset_id: UUID,
    name: str,
    fixture_id: UUID,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """A disallowed-lifecycle Asset still fixture-bound surfaces the binding error first."""
    state = _asset(asset_id=asset_id, name=name, lifecycle=source, fixture_id=fixture_id)
    with pytest.raises(AssetHasFixtureBindingError):
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=asset_id),
            context=_EMPTY_CONTEXT,
            now=now,
            decommissioned_by=_TEST_ACTOR_ID,
        )


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    name=printable_ascii_text(max_size=32),
    now=aware_datetimes(),
)
def test_decommission_asset_is_pure_same_input_same_output(
    asset_id: UUID,
    name: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    state = _asset(asset_id=asset_id, name=name, lifecycle=AssetLifecycle.ACTIVE)
    command = DecommissionAsset(asset_id=asset_id)
    first = decommission_asset.decide(
        state=state,
        command=command,
        context=_EMPTY_CONTEXT,
        now=now,
        decommissioned_by=_TEST_ACTOR_ID,
    )
    second = decommission_asset.decide(
        state=state,
        command=command,
        context=_EMPTY_CONTEXT,
        now=now,
        decommissioned_by=_TEST_ACTOR_ID,
    )
    assert first == second
