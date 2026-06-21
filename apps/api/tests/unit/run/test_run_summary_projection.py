"""Unit tests for RunSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 9
subscribed Run events (7 lifecycle + 2 cross-aggregate Campaign
membership events). Postgres-side behavior is in the integration
suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.run.projections import RunSummaryProjection

_RUN_ID = uuid4()
_PLAN_ID = uuid4()
_SUBJECT_ID = uuid4()
_CAMPAIGN_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 13, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Run",
        stream_id=_RUN_ID,
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
    proj = RunSummaryProjection()
    assert proj.name == "proj_run_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "RunStarted",
            "RunHeld",
            "RunResumed",
            "RunCompleted",
            "RunAborted",
            "RunStopped",
            "RunTruncated",
            "RunAddedToCampaign",
            "RunRemovedFromCampaign",
            "RunAdjusted",
        }
    )


@pytest.mark.unit
async def test_run_started_inserts_with_running_status_and_genesis_refs() -> None:
    """RunStarted carries plan_id, subject_id (optional), raid (optional)
    in the genesis payload; all surface in the projection at INSERT time."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "Tomography-2026-05-13-001",
            "plan_id": str(_PLAN_ID),
            "subject_id": str(_SUBJECT_ID),
            "raid": "https://raid.org/10.7935/test",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_run_summary" in sql
    assert "ON CONFLICT (run_id) DO NOTHING" in sql
    assert "'Running'" in sql
    # running_since is written at INSERT (= occurred_at, the Running start),
    # reusing the $6 created_at param so the positional args below are unchanged.
    assert "running_since" in sql
    assert args.args[1] == _RUN_ID
    assert args.args[2] == "Tomography-2026-05-13-001"
    assert args.args[3] == _PLAN_ID
    assert args.args[4] == _SUBJECT_ID
    assert args.args[5] == "https://raid.org/10.7935/test"
    assert args.args[6] == _NOW
    # 6g-c: override_parameters_present defaults FALSE for legacy
    # payloads (no override_parameters key in legacy events).
    assert args.args[7] is False
    # campaign_id defaults None for payloads without
    # the key (legacy streams or standalone Runs).
    assert args.args[8] is None

    # regression that drops or misorders the projection's UUID[]
    # parameter for pinned_calibration_ids fails loud at the unit tier
    # instead of slipping through to integration. Pre-12b RunStarted
    # payloads have no `pinned_calibration_ids` key; .get(..., []) lands
    # an empty UUID list.
    assert args.args[9] == []


@pytest.mark.unit
async def test_run_started_with_null_subject_id_for_calibration_run() -> None:
    """Calibration / dark-field Runs have subject_id=None."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "DarkField-cal",
            "plan_id": str(_PLAN_ID),
            "subject_id": None,
            "raid": None,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] is None  # subject_id
    assert args.args[5] is None  # raid


@pytest.mark.unit
async def test_run_started_sets_override_parameters_present_true_when_non_empty() -> None:
    """RunStarted with non-empty override_parameters payload sets the
    projection column TRUE."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "Run-with-overrides",
            "plan_id": str(_PLAN_ID),
            "subject_id": None,
            "raid": None,
            "override_parameters": {"energy": 12.0},
            "effective_parameters": {"energy": 12.0},
            "trigger_source": "operator:opid:5",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[7] is True  # override_parameters_present


@pytest.mark.unit
async def test_run_started_sets_override_parameters_present_false_when_empty() -> None:
    """Empty override_parameters payload (operator just used Plan
    defaults straight) keeps the projection column FALSE."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "Run-no-overrides",
            "plan_id": str(_PLAN_ID),
            "subject_id": None,
            "raid": None,
            "override_parameters": {},
            "effective_parameters": {"energy": 12.0},
            "trigger_source": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[7] is False


@pytest.mark.unit
@pytest.mark.parametrize(
    ("event_type", "expected_status"),
    [
        ("RunHeld", "Held"),
        ("RunCompleted", "Completed"),
        ("RunAborted", "Aborted"),
        ("RunStopped", "Stopped"),
        ("RunTruncated", "Truncated"),
    ],
)
async def test_lifecycle_transition_updates_status(event_type: str, expected_status: str) -> None:
    """Each generic lifecycle event writes its expected status via the shared
    status UPDATE. RunResumed is NOT here: it has a dedicated arm that also
    resets running_since (see test_run_resumed_sets_running_status_and_resets_running_since)."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        event_type,
        {"run_id": str(_RUN_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_run_summary" in sql
    assert "SET status = $2" in sql
    assert args.args[1] == _RUN_ID
    assert args.args[2] == expected_status


@pytest.mark.unit
async def test_run_resumed_sets_running_status_and_resets_running_since() -> None:
    """RunResumed flips status back to Running AND resets running_since to the
    resume timestamp, so the Run-liveness signal measures only the new Running
    interval (not the time spent Held)."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunResumed",
        {"run_id": str(_RUN_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_run_summary" in sql
    assert "status = 'Running'" in sql
    assert "running_since = $2" in sql
    assert args.args[1] == _RUN_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_run_started_with_campaign_id_inserts_with_membership() -> None:
    """When StartRun.campaign_id is set, the at-start membership lands
    on the projection row via the RunStarted payload's campaign_id
    field."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "Run-in-campaign",
            "plan_id": str(_PLAN_ID),
            "subject_id": None,
            "raid": None,
            "campaign_id": str(_CAMPAIGN_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[8] == _CAMPAIGN_ID


@pytest.mark.unit
async def test_run_campaign_assigned_updates_campaign_id() -> None:
    """Post-hoc add_run_to_campaign writes RunAddedToCampaign to the
    Run stream; the projection sets the campaign_id column to the
    event's campaign_id."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunAddedToCampaign",
        {
            "run_id": str(_RUN_ID),
            "campaign_id": str(_CAMPAIGN_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_run_summary" in sql
    assert "SET campaign_id = $2" in sql
    assert args.args[1] == _RUN_ID
    assert args.args[2] == _CAMPAIGN_ID


@pytest.mark.unit
async def test_run_campaign_unassigned_clears_campaign_id_to_null() -> None:
    """remove_run_from_campaign writes RunRemovedFromCampaign to the
    Run stream; the projection clears campaign_id to NULL (the prior
    campaign_id stays on the event payload for audit-replay, not in
    the read model)."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunRemovedFromCampaign",
        {
            "run_id": str(_RUN_ID),
            "campaign_id": str(_CAMPAIGN_ID),
            "reason": "wrong campaign at start",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_run_summary" in sql
    assert "SET campaign_id = $2" in sql
    assert args.args[1] == _RUN_ID
    assert args.args[2] is None


@pytest.mark.unit
async def test_unknown_event_type_falls_through() -> None:
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


# ---------- pinned_calibration_ids args[9] binding ----------


@pytest.mark.unit
async def test_run_started_without_pinned_calibration_ids_key_falls_back_to_empty_list() -> None:
    """Legacy RunStarted events lack the `pinned_calibration_ids` key
    in the payload entirely. The projection's `payload.get(
    "pinned_calibration_ids", [])` fallback MUST land an empty UUID list
    on the column so legacy rows backfill cleanly (matches the
    in-memory frozenset default + the from_stored forward-compat
    fold). Mirror of Data BC's
    test_dataset_registered_without_used_calibration_ids_key_falls_back_to_empty_list."""
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "legacy-run",
            "plan_id": str(_PLAN_ID),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: pinned_calibration_ids deliberately ABSENT
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[9] == []


@pytest.mark.unit
async def test_run_started_with_pinned_calibration_ids_inserts_uuid_array() -> None:
    """When the payload carries `pinned_calibration_ids`, the projection
    parses each entry into a UUID and passes the list as the 9th arg.
    The decider sorts before emit; the projection passes through
    verbatim. Mirror of Data BC's
    test_dataset_registered_with_citations_inserts_uuid_array."""
    pin_a = uuid4()
    pin_b = uuid4()
    proj = RunSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {
            "run_id": str(_RUN_ID),
            "name": "pinned-run",
            "plan_id": str(_PLAN_ID),
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # Sorted (decider's responsibility); projection trusts.
            "pinned_calibration_ids": sorted([str(pin_a), str(pin_b)]),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    # Each entry parsed back into UUID and passed to the SQL execute.
    pinned: list[Any] = args.args[9]
    assert isinstance(pinned, list)
    assert set(pinned) == {pin_a, pin_b}
