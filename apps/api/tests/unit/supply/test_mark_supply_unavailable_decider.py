"""Pure-decider tests for `mark_supply_unavailable` slice (10a-b).

Multi-source guard (widest source set): `{Unknown, Available,
Degraded, Recovering}`. Only Unavailable itself is excluded
(strict-not-idempotent).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    InvalidSupplyReasonError,
    Supply,
    SupplyCannotMarkUnavailableError,
    SupplyMarkedUnavailable,
    SupplyName,
    SupplyNotFoundError,
    SupplyScope,
    SupplyStatus,
)
from cora.supply.features import mark_supply_unavailable
from cora.supply.features.mark_supply_unavailable import MarkSupplyUnavailable

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = uuid4()
_ACTOR_ID = ActorId(uuid4())


def _supply(status: SupplyStatus) -> Supply:
    return Supply(
        id=_SUPPLY_ID,
        scope=SupplyScope.BEAMLINE,
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2"),
        status=status,
    )


@pytest.mark.parametrize(
    "current_status",
    [
        SupplyStatus.UNKNOWN,
        SupplyStatus.AVAILABLE,
        SupplyStatus.DEGRADED,
        SupplyStatus.RECOVERING,
    ],
)
@pytest.mark.unit
def test_decide_emits_event_from_any_non_unavailable_status(
    current_status: SupplyStatus,
) -> None:
    events = mark_supply_unavailable.decide(
        state=_supply(current_status),
        command=MarkSupplyUnavailable(supply_id=_SUPPLY_ID, reason="beam dump"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events == [
        SupplyMarkedUnavailable(
            supply_id=_SUPPLY_ID,
            from_status=current_status.value,
            reason="beam dump",
            trigger="Operator",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_rejects_when_already_unavailable() -> None:
    """Strict-not-idempotent: re-marking Unavailable raises."""
    with pytest.raises(SupplyCannotMarkUnavailableError) as exc_info:
        mark_supply_unavailable.decide(
            state=_supply(SupplyStatus.UNAVAILABLE),
            command=MarkSupplyUnavailable(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
    assert exc_info.value.current_status == SupplyStatus.UNAVAILABLE


@pytest.mark.unit
def test_decide_rejects_when_supply_not_found() -> None:
    with pytest.raises(SupplyNotFoundError):
        mark_supply_unavailable.decide(
            state=None,
            command=MarkSupplyUnavailable(supply_id=_SUPPLY_ID, reason="r"),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )


@pytest.mark.unit
def test_decide_trims_reason() -> None:
    events = mark_supply_unavailable.decide(
        state=_supply(SupplyStatus.AVAILABLE),
        command=MarkSupplyUnavailable(supply_id=_SUPPLY_ID, reason="  beam dump  "),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].reason == "beam dump"


@pytest.mark.unit
def test_decide_hardcodes_trigger_to_operator() -> None:
    events = mark_supply_unavailable.decide(
        state=_supply(SupplyStatus.AVAILABLE),
        command=MarkSupplyUnavailable(supply_id=_SUPPLY_ID, reason="r"),
        now=_NOW,
        triggered_by=_ACTOR_ID,
    )
    assert events[0].trigger == "Operator"


@pytest.mark.unit
def test_decide_rejects_empty_reason() -> None:
    with pytest.raises(InvalidSupplyReasonError):
        mark_supply_unavailable.decide(
            state=_supply(SupplyStatus.AVAILABLE),
            command=MarkSupplyUnavailable(supply_id=_SUPPLY_ID, reason=""),
            now=_NOW,
            triggered_by=_ACTOR_ID,
        )
