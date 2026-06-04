"""Unit tests for DecisionSummaryProjection.

Decision is single-event-genesis (one DecisionRegistered = one
projection row, no transitions). Tests pin the genesis INSERT path
including the denormalized confidence_band derivation, plus the
`DecisionLogbook*` events being intentionally NOT subscribed.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.decision.projections import DecisionSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_DECISION_ID = uuid4()
_ACTOR_ID = uuid4()
_PARENT_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 13, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Decision",
        stream_id=_DECISION_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = DecisionSummaryProjection()
    assert proj.name == "proj_decision_summary"
    # ONLY DecisionRegistered; logbook events are intentionally excluded.
    assert proj.subscribed_event_types == frozenset({"DecisionRegistered"})


@pytest.mark.unit
async def test_decision_logbook_events_are_not_subscribed() -> None:
    """DecisionLogbookOpened/Closed are internal logbook bookkeeping
    that doesn't mutate the decision-summary projection. Pinned so a
    future refactor doesn't accidentally subscribe them."""
    proj = DecisionSummaryProjection()
    assert "DecisionLogbookOpened" not in proj.subscribed_event_types
    assert "DecisionLogbookClosed" not in proj.subscribed_event_types


@pytest.mark.unit
async def test_decision_registered_inserts_with_genesis_payload() -> None:
    proj = DecisionSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "DecisionRegistered",
        {
            "decision_id": str(_DECISION_ID),
            "actor_id": str(_ACTOR_ID),
            "context": "calibration interlock check",
            "choice": "accept",
            "parent_id": None,
            "override_kind": None,
            "rule": "auto-accept",
            "reasoning": None,
            "confidence": 0.97,
            "confidence_source": "ensemble",
            "alternatives": [],
            "inputs": None,
            "reasoning_signature": None,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_decision_summary" in sql
    assert "ON CONFLICT (decision_id) DO NOTHING" in sql
    assert args.args[1] == _DECISION_ID
    assert args.args[2] == _ACTOR_ID
    assert args.args[3] == "auto-accept"  # rule
    assert args.args[4] is None  # parent_id
    assert args.args[5] == 0.97  # confidence
    assert args.args[6] == "Certain"  # confidence_band derived (>=0.95)
    assert args.args[7] == "accept"  # choice
    assert args.args[8] == _NOW


@pytest.mark.unit
@pytest.mark.parametrize(
    ("confidence", "expected_band"),
    [
        (0.1, "Low"),
        (0.5, "Medium"),
        (0.8, "High"),
        (0.99, "Certain"),
        (None, None),
    ],
)
async def test_confidence_band_derivation_at_insert(
    confidence: float | None, expected_band: str | None
) -> None:
    """The projection precomputes confidence_band from the float at
    INSERT time so categorical filtering is a fast indexed lookup
    instead of recomputing on every read."""
    proj = DecisionSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "DecisionRegistered",
        {
            "decision_id": str(_DECISION_ID),
            "actor_id": str(_ACTOR_ID),
            "confidence": confidence,
            "choice": "NominalCompletion",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[5] == confidence
    assert args.args[6] == expected_band


@pytest.mark.unit
async def test_decision_with_parent_id_persists_override_chain_link() -> None:
    proj = DecisionSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "DecisionRegistered",
        {
            "decision_id": str(_DECISION_ID),
            "actor_id": str(_ACTOR_ID),
            "parent_id": str(_PARENT_ID),
            "confidence": None,
            "choice": "NominalCompletion",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] == _PARENT_ID


@pytest.mark.unit
async def test_decision_with_audit_only_choice_persists_for_filter_visibility() -> None:
    """`DebriefConflicted` (audit-only, emitted by the loser agent in
    the cross-agent debrief lease) is projected like any other choice.
    The list_decisions surface exposes a `choice` filter so analytic
    callers can drop these rows from outcome-rate denominators."""
    proj = DecisionSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "DecisionRegistered",
        {
            "decision_id": str(_DECISION_ID),
            "actor_id": str(_ACTOR_ID),
            "confidence": None,
            "choice": "DebriefConflicted",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[7] == "DebriefConflicted"


@pytest.mark.unit
async def test_unknown_event_type_falls_through() -> None:
    proj = DecisionSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_logbook_opened_is_silently_dropped() -> None:
    """DecisionLogbookOpened isn't in subscribed_event_types so the
    SQL filter prevents it from reaching apply(), but if it ever
    did the bare drop branch should not crash."""
    proj = DecisionSummaryProjection()
    conn = AsyncMock()
    event = _stored("DecisionLogbookOpened", {"decision_id": str(_DECISION_ID)})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
