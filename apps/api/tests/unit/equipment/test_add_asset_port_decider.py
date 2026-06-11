"""Unit tests for the `add_asset_port` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotAddPortError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetPort,
    AssetPortAdded,
    AssetTier,
    InvalidAssetPortNameError,
    InvalidAssetPortSignalTypeError,
    PortDirection,
)
from cora.equipment.features import add_asset_port
from cora.equipment.features.add_asset_port import AddAssetPort

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    ports: frozenset[AssetPort] = frozenset(),
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("Detector-X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        ports=ports,
    )


@pytest.mark.unit
def test_decide_emits_event_when_adding_first_port() -> None:
    state = _asset()
    events = add_asset_port.decide(
        state=state,
        command=AddAssetPort(
            asset_id=state.id,
            port_name="trigger_in",
            direction=PortDirection.INPUT,
            signal_type="TTL",
        ),
        now=_NOW,
    )
    assert events == [
        AssetPortAdded(
            asset_id=state.id,
            port_name="trigger_in",
            direction="Input",
            signal_type="TTL",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        add_asset_port.decide(
            state=None,
            command=AddAssetPort(
                asset_id=target_id,
                port_name="x",
                direction=PortDirection.INPUT,
                signal_type="TTL",
            ),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_add_when_asset_decommissioned() -> None:
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    with pytest.raises(AssetCannotAddPortError) as exc_info:
        add_asset_port.decide(
            state=state,
            command=AddAssetPort(
                asset_id=state.id,
                port_name="trigger_in",
                direction=PortDirection.INPUT,
                signal_type="TTL",
            ),
            now=_NOW,
        )
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
def test_decide_raises_cannot_add_when_port_name_already_exists() -> None:
    """Strict-not-idempotent: same name reject regardless of
    direction/signal_type differences."""
    existing = AssetPort(name="trigger", direction=PortDirection.INPUT, signal_type="TTL")
    state = _asset(ports=frozenset({existing}))
    with pytest.raises(AssetCannotAddPortError) as exc_info:
        add_asset_port.decide(
            state=state,
            command=AddAssetPort(
                asset_id=state.id,
                port_name="trigger",
                direction=PortDirection.OUTPUT,  # different direction
                signal_type="LVDS",  # different signal type
            ),
            now=_NOW,
        )
    assert "trigger" in exc_info.value.reason
    assert "strict-not-idempotent" in exc_info.value.reason


@pytest.mark.unit
def test_decide_propagates_invalid_port_name_error_from_vo() -> None:
    """Empty name surfaces as InvalidAssetPortNameError (mapped to
    HTTP 400 by the route's exception handler)."""
    state = _asset()
    with pytest.raises(InvalidAssetPortNameError):
        add_asset_port.decide(
            state=state,
            command=AddAssetPort(
                asset_id=state.id,
                port_name="",
                direction=PortDirection.INPUT,
                signal_type="TTL",
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_propagates_invalid_signal_type_error_from_vo() -> None:
    state = _asset()
    with pytest.raises(InvalidAssetPortSignalTypeError):
        add_asset_port.decide(
            state=state,
            command=AddAssetPort(
                asset_id=state.id,
                port_name="trigger",
                direction=PortDirection.INPUT,
                signal_type="",
            ),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
    ],
)
def test_decide_succeeds_for_every_non_decommissioned_lifecycle(
    lifecycle: AssetLifecycle,
) -> None:
    state = _asset(lifecycle=lifecycle)
    events = add_asset_port.decide(
        state=state,
        command=AddAssetPort(
            asset_id=state.id,
            port_name="x",
            direction=PortDirection.INPUT,
            signal_type="TTL",
        ),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_allows_two_ports_with_same_signal_type_different_names() -> None:
    """Two TTL inputs with different names is fine."""
    existing = AssetPort(name="trigger_a", direction=PortDirection.INPUT, signal_type="TTL")
    state = _asset(ports=frozenset({existing}))
    events = add_asset_port.decide(
        state=state,
        command=AddAssetPort(
            asset_id=state.id,
            port_name="trigger_b",
            direction=PortDirection.INPUT,
            signal_type="TTL",
        ),
        now=_NOW,
    )
    assert len(events) == 1
