"""Decider tests for `observe_supply_status` (memo 2 / Port B).

Pins the Monitor truth table per
[[project_supply_monitor_trigger_design]]:
  - Permitted target statuses: Degraded, Unavailable, Recovering
  - Forbidden target statuses (operator-only):
      * Available (latched-alarm / first-observation declaration)
      * Decommissioned (no Monitor equivalent for deregister)
  - Source-state allowlists mirror the operator-driven sibling
    deciders verbatim.
  - Every emitted event carries `trigger="Monitor"`, a typed
    `MonitorSourceId` in `triggered_by`, and a serialized
    `monitor_ref` audit field.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.shared.identity import MonitorSourceId
from cora.supply.aggregates.supply import (
    InvalidSupplyReasonError,
    MonitorRef,
    MonitorTriggerNotPermittedError,
    Supply,
    SupplyCannotDegradeError,
    SupplyCannotMarkRecoveringError,
    SupplyCannotMarkUnavailableError,
    SupplyDegraded,
    SupplyMarkedRecovering,
    SupplyMarkedUnavailable,
    SupplyName,
    SupplyNotFoundError,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features.observe_supply_status import ObserveSupplyStatus, decide

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
_MREF = MonitorRef(source_kind="EpicsPv", source_id="S35:beam_current")
_MONITOR_SOURCE_ID = MonitorSourceId(uuid4())


def _state(status: SupplyStatus) -> Supply:
    return Supply(
        id=uuid4(),
        scope=SupplyScope.BEAMLINE,
        kind="PhotonBeam",
        name=SupplyName("beam"),
        status=status,
    )


def _cmd(
    supply_id: UUID, new_status: SupplyStatus, reason: str = "sensor said"
) -> ObserveSupplyStatus:
    return ObserveSupplyStatus(
        supply_id=supply_id,
        new_status=new_status,
        monitor_ref=_MREF,
        monitor_source_id=_MONITOR_SOURCE_ID,
        reason=reason,
    )


@pytest.mark.unit
def test_decide_raises_not_found_when_state_is_none() -> None:
    sup_id = uuid4()
    with pytest.raises(SupplyNotFoundError):
        decide(None, _cmd(sup_id, SupplyStatus.DEGRADED), now=_NOW, triggered_by=_MONITOR_SOURCE_ID)


@pytest.mark.unit
@pytest.mark.parametrize(
    "forbidden_target",
    [SupplyStatus.AVAILABLE, SupplyStatus.DECOMMISSIONED, SupplyStatus.UNKNOWN],
)
def test_decide_rejects_monitor_forbidden_target_status(forbidden_target: SupplyStatus) -> None:
    """Available + Decommissioned are operator-only target statuses for
    Monitor; Unknown is reachable only via genesis (defensive guard)."""
    s = _state(SupplyStatus.AVAILABLE)
    with pytest.raises(MonitorTriggerNotPermittedError) as exc_info:
        decide(s, _cmd(s.id, forbidden_target), now=_NOW, triggered_by=_MONITOR_SOURCE_ID)
    assert exc_info.value.requested_status is forbidden_target


@pytest.mark.unit
@pytest.mark.parametrize(
    "source", [SupplyStatus.UNKNOWN, SupplyStatus.AVAILABLE, SupplyStatus.RECOVERING]
)
def test_decide_degraded_from_permitted_source(source: SupplyStatus) -> None:
    s = _state(source)
    events = decide(s, _cmd(s.id, SupplyStatus.DEGRADED), now=_NOW, triggered_by=_MONITOR_SOURCE_ID)
    assert len(events) == 1
    assert isinstance(events[0], SupplyDegraded)
    assert events[0].trigger == "Monitor"
    assert events[0].triggered_by == _MONITOR_SOURCE_ID
    assert events[0].monitor_ref == "EpicsPv:S35:beam_current"
    assert events[0].from_status == source.value


@pytest.mark.unit
def test_decide_degraded_from_disallowed_source_raises() -> None:
    """Source-state allowlist for Degraded matches operator-driven slice."""
    s = _state(SupplyStatus.UNAVAILABLE)
    with pytest.raises(SupplyCannotDegradeError):
        decide(s, _cmd(s.id, SupplyStatus.DEGRADED), now=_NOW, triggered_by=_MONITOR_SOURCE_ID)


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        SupplyStatus.UNKNOWN,
        SupplyStatus.AVAILABLE,
        SupplyStatus.DEGRADED,
        SupplyStatus.RECOVERING,
    ],
)
def test_decide_unavailable_from_permitted_source(source: SupplyStatus) -> None:
    s = _state(source)
    events = decide(
        s, _cmd(s.id, SupplyStatus.UNAVAILABLE), now=_NOW, triggered_by=_MONITOR_SOURCE_ID
    )
    assert len(events) == 1
    assert isinstance(events[0], SupplyMarkedUnavailable)
    assert events[0].trigger == "Monitor"
    assert events[0].triggered_by == _MONITOR_SOURCE_ID


@pytest.mark.unit
def test_decide_unavailable_from_disallowed_source_raises() -> None:
    """Only Unavailable itself disallows the Unavailable target."""
    s = _state(SupplyStatus.UNAVAILABLE)
    with pytest.raises(SupplyCannotMarkUnavailableError):
        decide(s, _cmd(s.id, SupplyStatus.UNAVAILABLE), now=_NOW, triggered_by=_MONITOR_SOURCE_ID)


@pytest.mark.unit
def test_decide_recovering_from_unavailable_succeeds() -> None:
    s = _state(SupplyStatus.UNAVAILABLE)
    events = decide(
        s, _cmd(s.id, SupplyStatus.RECOVERING), now=_NOW, triggered_by=_MONITOR_SOURCE_ID
    )
    assert len(events) == 1
    assert isinstance(events[0], SupplyMarkedRecovering)
    assert events[0].trigger == "Monitor"
    assert events[0].triggered_by == _MONITOR_SOURCE_ID


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        SupplyStatus.UNKNOWN,
        SupplyStatus.AVAILABLE,
        SupplyStatus.DEGRADED,
        SupplyStatus.RECOVERING,
    ],
)
def test_decide_recovering_from_disallowed_source_raises(source: SupplyStatus) -> None:
    """Recovering's source allowlist is {Unavailable} only."""
    s = _state(source)
    with pytest.raises(SupplyCannotMarkRecoveringError):
        decide(s, _cmd(s.id, SupplyStatus.RECOVERING), now=_NOW, triggered_by=_MONITOR_SOURCE_ID)


@pytest.mark.unit
def test_decide_invalid_reason_raises() -> None:
    s = _state(SupplyStatus.AVAILABLE)
    with pytest.raises(InvalidSupplyReasonError):
        decide(
            s,
            _cmd(s.id, SupplyStatus.DEGRADED, reason="   "),
            now=_NOW,
            triggered_by=_MONITOR_SOURCE_ID,
        )
