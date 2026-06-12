"""Property-based tests for `add_asset_port.decide` (Equipment BC).

Complements the example-based `test_add_asset_port_decider.py` with
universal claims across generated inputs. The decider is a pure
in-place port-set mutation

    (state, command, now) -> list[AssetPortAdded]

Load-bearing properties:

  - state=None always raises `AssetNotFoundError` carrying command.asset_id.
  - The lifecycle partition is total over `AssetLifecycle`: only
    `Decommissioned` is disqualifying and raises `AssetCannotAddPortError`
    (reason naming the retired state); every non-Decommissioned lifecycle
    emits exactly one `AssetPortAdded` (asset_id=state.id, occurred_at=now),
    so a future lifecycle value cannot silently fall through.
  - The emitted event's asset_id is `state.id`, never `command.asset_id`.
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
    AssetCannotAddPortError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetPort,
    AssetPortAdded,
    AssetTier,
    PortDirection,
)
from cora.equipment.features import add_asset_port
from cora.equipment.features.add_asset_port import AddAssetPort
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_PORT_NAME = "trigger_in"
_SIGNAL_TYPE = "TTL"

_ALLOWED_SOURCES = tuple(
    lifecycle for lifecycle in AssetLifecycle if lifecycle is not AssetLifecycle.DECOMMISSIONED
)
_DISALLOWED_SOURCES = (AssetLifecycle.DECOMMISSIONED,)


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
        parent_id=UUID(int=7),
        lifecycle=lifecycle,
        ports=ports,
    )


@pytest.mark.unit
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_add_asset_port_with_none_state_always_raises_not_found(
    asset_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `AssetNotFoundError` carrying command.asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        add_asset_port.decide(
            state=None,
            command=AddAssetPort(
                asset_id=asset_id,
                port_name=_PORT_NAME,
                direction=PortDirection.INPUT,
                signal_type=_SIGNAL_TYPE,
            ),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    source=st.sampled_from(_ALLOWED_SOURCES),
    direction=st.sampled_from(PortDirection),
    now=aware_datetimes(),
)
def test_add_asset_port_from_allowed_lifecycle_emits_single_event(
    asset_id: UUID,
    source: AssetLifecycle,
    direction: PortDirection,
    now: datetime,
) -> None:
    """Any non-Decommissioned lifecycle emits exactly one AssetPortAdded."""
    events = add_asset_port.decide(
        state=_asset(asset_id=asset_id, lifecycle=source),
        command=AddAssetPort(
            asset_id=asset_id,
            port_name=_PORT_NAME,
            direction=direction,
            signal_type=_SIGNAL_TYPE,
        ),
        now=now,
    )
    assert events == [
        AssetPortAdded(
            asset_id=asset_id,
            port_name=_PORT_NAME,
            direction=direction.value,
            signal_type=_SIGNAL_TYPE,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_add_asset_port_from_decommissioned_always_raises_cannot_add(
    asset_id: UUID,
    source: AssetLifecycle,
    now: datetime,
) -> None:
    """A Decommissioned asset raises, with a reason naming the retired state."""
    with pytest.raises(AssetCannotAddPortError) as exc:
        add_asset_port.decide(
            state=_asset(asset_id=asset_id, lifecycle=source),
            command=AddAssetPort(
                asset_id=asset_id,
                port_name=_PORT_NAME,
                direction=PortDirection.INPUT,
                signal_type=_SIGNAL_TYPE,
            ),
            now=now,
        )
    assert AssetLifecycle.DECOMMISSIONED.value in exc.value.reason


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    port_name=printable_ascii_text(max_size=100),
    now=aware_datetimes(),
)
def test_add_asset_port_with_existing_name_always_raises_cannot_add(
    asset_id: UUID,
    port_name: str,
    now: datetime,
) -> None:
    """Strict-not-idempotent: a name already in state.ports raises, naming the port."""
    existing = AssetPort(
        name=port_name,
        direction=PortDirection.INPUT,
        signal_type=_SIGNAL_TYPE,
    )
    with pytest.raises(AssetCannotAddPortError) as exc:
        add_asset_port.decide(
            state=_asset(asset_id=asset_id, ports=frozenset({existing})),
            command=AddAssetPort(
                asset_id=asset_id,
                port_name=port_name,
                direction=PortDirection.OUTPUT,
                signal_type="LVDS",
            ),
            now=now,
        )
    assert exc.value.port_name == existing.name


@pytest.mark.unit
@given(state_asset_id=st.uuids(), command_asset_id=st.uuids(), now=aware_datetimes())
def test_add_asset_port_emits_event_with_state_id_not_command_id(
    state_asset_id: UUID,
    command_asset_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's asset_id is state.id, not command.asset_id."""
    assume(state_asset_id != command_asset_id)
    events = add_asset_port.decide(
        state=_asset(asset_id=state_asset_id),
        command=AddAssetPort(
            asset_id=command_asset_id,
            port_name=_PORT_NAME,
            direction=PortDirection.INPUT,
            signal_type=_SIGNAL_TYPE,
        ),
        now=now,
    )
    assert events[0].asset_id == state_asset_id


@pytest.mark.unit
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_add_asset_port_is_pure_same_input_same_output(asset_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _asset(asset_id=asset_id)
    command = AddAssetPort(
        asset_id=asset_id,
        port_name=_PORT_NAME,
        direction=PortDirection.INPUT,
        signal_type=_SIGNAL_TYPE,
    )
    first = add_asset_port.decide(state=state, command=command, now=now)
    second = add_asset_port.decide(state=state, command=command, now=now)
    assert first == second
