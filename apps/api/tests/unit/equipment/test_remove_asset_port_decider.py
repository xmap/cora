"""Unit tests for the `remove_asset_port` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

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
def test_decide_emits_event_when_removing_existing_port() -> None:
    port = AssetPort(name="trigger", direction=PortDirection.INPUT, signal_type="TTL")
    state = _asset(ports=frozenset({port}))
    events = remove_asset_port.decide(
        state=state,
        command=RemoveAssetPort(asset_id=state.id, port_name="trigger"),
        now=_NOW,
    )
    assert events == [AssetPortRemoved(asset_id=state.id, port_name="trigger", occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        remove_asset_port.decide(
            state=None,
            command=RemoveAssetPort(asset_id=target_id, port_name="x"),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_remove_when_asset_decommissioned() -> None:
    port = AssetPort(name="trigger", direction=PortDirection.INPUT, signal_type="TTL")
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED, ports=frozenset({port}))
    with pytest.raises(AssetCannotRemovePortError) as exc_info:
        remove_asset_port.decide(
            state=state,
            command=RemoveAssetPort(asset_id=state.id, port_name="trigger"),
            now=_NOW,
        )
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
def test_decide_raises_cannot_remove_when_port_name_not_found() -> None:
    """Strict-not-idempotent: removing a non-existent port raises."""
    port = AssetPort(name="trigger", direction=PortDirection.INPUT, signal_type="TTL")
    state = _asset(ports=frozenset({port}))
    with pytest.raises(AssetCannotRemovePortError) as exc_info:
        remove_asset_port.decide(
            state=state,
            command=RemoveAssetPort(asset_id=state.id, port_name="nonexistent"),
            now=_NOW,
        )
    assert "nonexistent" in exc_info.value.reason
    assert "strict-not-idempotent" in exc_info.value.reason


@pytest.mark.unit
def test_decide_removes_only_named_port_when_multiple_exist() -> None:
    """The decider's job is to emit AssetPortRemoved with the
    matched name; the evolver removes by name, leaving siblings."""
    port_a = AssetPort(name="a", direction=PortDirection.INPUT, signal_type="TTL")
    port_b = AssetPort(name="b", direction=PortDirection.OUTPUT, signal_type="TTL")
    state = _asset(ports=frozenset({port_a, port_b}))
    events = remove_asset_port.decide(
        state=state,
        command=RemoveAssetPort(asset_id=state.id, port_name="a"),
        now=_NOW,
    )
    assert events == [AssetPortRemoved(asset_id=state.id, port_name="a", occurred_at=_NOW)]
