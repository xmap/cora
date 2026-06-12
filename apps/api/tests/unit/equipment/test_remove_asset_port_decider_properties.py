"""Property-based tests for `remove_asset_port.decide` (Equipment BC).

Complements the example-based `test_remove_asset_port_decider.py` with
universal claims across generated inputs. The decider is a pure
in-place mutation

    (state, command, now) -> list[AssetPortRemoved]

Load-bearing properties:

  - state=None always raises `AssetNotFoundError` carrying
    command.asset_id.
  - The lifecycle partition: a `Decommissioned` asset always raises
    `AssetCannotRemovePortError` (carrying state.id and the trimmed
    port name) even when the named port exists.
  - The strict-not-idempotent partition: any non-Decommissioned
    lifecycle with the named port absent raises
    `AssetCannotRemovePortError`.
  - The happy partition: across every non-Decommissioned lifecycle,
    an asset whose port set contains the named port emits exactly one
    `AssetPortRemoved` (asset_id=state.id, occurred_at=now).
  - The emitted event's asset_id is `state.id`, never command.asset_id.
  - The emitted port_name is the command's name after `.strip()`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotRemovePortError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetPort,
    AssetPortRemoved,
    AssetTier,
    PortDirection,
)
from cora.equipment.features import remove_asset_port
from cora.equipment.features.remove_asset_port import RemoveAssetPort
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_PARENT_ID = UUID(int=1)
_PORT_NAME = "trigger"

_REMOVABLE_SOURCES = tuple(s for s in AssetLifecycle if s is not AssetLifecycle.DECOMMISSIONED)


def _asset(
    *,
    asset_id: UUID,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    ports: frozenset[AssetPort] = frozenset(),
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Detector-X"),
        tier=AssetTier.DEVICE,
        parent_id=_PARENT_ID,
        lifecycle=lifecycle,
        ports=ports,
    )


def _port(name: str = _PORT_NAME) -> AssetPort:
    return AssetPort(name=name, direction=PortDirection.INPUT, signal_type="TTL")


@pytest.mark.unit
@given(asset_id=st.uuids(), port_name=printable_ascii_text(max_size=20), now=aware_datetimes())
def test_remove_port_with_none_state_always_raises_not_found(
    asset_id: UUID,
    port_name: str,
    now: datetime,
) -> None:
    """Empty stream always raises `AssetNotFoundError` carrying command.asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        remove_asset_port.decide(
            state=None,
            command=RemoveAssetPort(asset_id=asset_id, port_name=port_name),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_remove_port_from_decommissioned_always_raises_cannot_remove(
    asset_id: UUID,
    now: datetime,
) -> None:
    """A Decommissioned asset raises even when the named port exists."""
    state = _asset(
        asset_id=asset_id,
        lifecycle=AssetLifecycle.DECOMMISSIONED,
        ports=frozenset({_port()}),
    )
    with pytest.raises(AssetCannotRemovePortError) as exc:
        remove_asset_port.decide(
            state=state,
            command=RemoveAssetPort(asset_id=asset_id, port_name=_PORT_NAME),
            now=now,
        )
    assert AssetLifecycle.DECOMMISSIONED.value in exc.value.reason


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    source=st.sampled_from(_REMOVABLE_SOURCES),
    now=aware_datetimes(),
)
def test_remove_absent_port_always_raises_cannot_remove(
    asset_id: UUID,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """Strict-not-idempotent: removing an absent port raises across allowed lifecycles."""
    state = _asset(asset_id=asset_id, lifecycle=source, ports=frozenset())
    with pytest.raises(AssetCannotRemovePortError) as exc:
        remove_asset_port.decide(
            state=state,
            command=RemoveAssetPort(asset_id=asset_id, port_name=_PORT_NAME),
            now=now,
        )
    assert "strict-not-idempotent" in exc.value.reason


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    source=st.sampled_from(_REMOVABLE_SOURCES),
    now=aware_datetimes(),
)
def test_remove_existing_port_emits_single_event(
    asset_id: UUID,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """Across every non-Decommissioned lifecycle, removing a present port emits one event."""
    state = _asset(asset_id=asset_id, lifecycle=source, ports=frozenset({_port()}))
    events = remove_asset_port.decide(
        state=state,
        command=RemoveAssetPort(asset_id=asset_id, port_name=_PORT_NAME),
        now=now,
    )
    assert events == [AssetPortRemoved(asset_id=asset_id, port_name=_PORT_NAME, occurred_at=now)]


@pytest.mark.unit
@given(state_id=st.uuids(), command_asset_id=st.uuids(), now=aware_datetimes())
def test_remove_existing_port_emits_event_with_state_id(
    state_id: UUID,
    command_asset_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's asset_id is state.id, not command.asset_id."""
    assume(state_id != command_asset_id)
    state = _asset(asset_id=state_id, ports=frozenset({_port()}))
    events = remove_asset_port.decide(
        state=state,
        command=RemoveAssetPort(asset_id=command_asset_id, port_name=_PORT_NAME),
        now=now,
    )
    assert events[0].asset_id == state_id


@pytest.mark.unit
@given(asset_id=st.uuids(), name=printable_ascii_text(max_size=20), now=aware_datetimes())
def test_remove_existing_port_emits_event_with_trimmed_name(
    asset_id: UUID,
    name: str,
    now: datetime,
) -> None:
    """The emitted port_name is the command's name after `.strip()`."""
    state = _asset(asset_id=asset_id, ports=frozenset({_port(name)}))
    events = remove_asset_port.decide(
        state=state,
        command=RemoveAssetPort(asset_id=asset_id, port_name=f"  {name}  "),
        now=now,
    )
    assert events[0].port_name == name


@pytest.mark.unit
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_remove_port_is_pure_same_input_same_output(
    asset_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _asset(asset_id=asset_id, ports=frozenset({_port()}))
    command = RemoveAssetPort(asset_id=asset_id, port_name=_PORT_NAME)
    first = remove_asset_port.decide(state=state, command=command, now=now)
    second = remove_asset_port.decide(state=state, command=command, now=now)
    assert first == second
