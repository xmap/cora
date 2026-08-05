"""Unit tests for ActorSummaryProjection.

Pins per-event-type apply() dispatch + idempotency. Postgres-side
behavior is exercised in `tests/integration/test_projection_worker_postgres.py`.

Post PII vault: the projection subscribes to BOTH the V1 legacy
"ActorRegistered" discriminator (payload carries `name`) and the
post-vault "ActorRegisteredV2" discriminator (payload omits `name`;
projection pulls the name from `actor_profile` via sub-SELECT in
the INSERT SQL).
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.access.projections import ActorSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_ACTOR_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Actor",
        stream_id=_ACTOR_ID,
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
    proj = ActorSummaryProjection()
    assert proj.name == "proj_access_actor_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "ActorRegistered",
            "ActorRegisteredV2",
            "ActorDeactivated",
            "ActorReactivated",
            "ActorProfileForgotten",
        }
    )


@pytest.mark.unit
async def test_actor_registered_v2_inserts_with_subquery_to_actor_profile() -> None:
    """V2 (PII vault) payload has no `name`; the projection's INSERT
    SQL pulls `name` from actor_profile via a sub-SELECT bound at
    apply-time (the upsert runs before the event becomes visible
    via the handler's pre-append vault write)."""
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorRegisteredV2",
        {
            "actor_id": str(_ACTOR_ID),
            "occurred_at": _NOW.isoformat(),
            "kind": "human",
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_access_actor_summary" in sql
    assert "actor_profile" in sql
    assert "ON CONFLICT (actor_id) DO NOTHING" in sql
    # V2 binds 3 positional args: actor_id, kind, created_at.
    assert args.args[1] == _ACTOR_ID
    assert args.args[2] == "human"
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_actor_registered_v1_legacy_inserts_with_payload_name() -> None:
    """V1 legacy payload still carries `name` — the legacy arm uses
    it directly (no JOIN). Mirrors `from_stored`'s legacy arm
    dropping the field; same pattern, two homes."""
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorRegistered",
        {
            "actor_id": str(_ACTOR_ID),
            "name": "Doga",
            "occurred_at": _NOW.isoformat(),
            "kind": "human",
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_access_actor_summary" in sql
    assert "ON CONFLICT (actor_id) DO NOTHING" in sql
    assert args.args[1] == _ACTOR_ID
    assert args.args[2] == "Doga"
    assert args.args[3] == "human"
    assert args.args[4] == _NOW


@pytest.mark.unit
async def test_actor_registered_v2_agent_kind_inserts_correctly() -> None:
    """Cross-BC define_agent V2 write: kind=agent flows through the projection."""
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorRegisteredV2",
        {
            "actor_id": str(_ACTOR_ID),
            "occurred_at": _NOW.isoformat(),
            "kind": "agent",
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] == "agent"


@pytest.mark.unit
async def test_actor_registered_v1_payload_without_kind_falls_back_to_human() -> None:
    """Forward-compat: the oldest legacy V1 payloads without the
    `kind` field fall back to kind=human (matches `from_stored`'s
    default)."""
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorRegistered",
        {
            "actor_id": str(_ACTOR_ID),
            "name": "Doga",
            "occurred_at": _NOW.isoformat(),
            # No "kind" field; oldest legacy payload shape.
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    assert args.args[3] == "human"


@pytest.mark.unit
async def test_actor_reactivated_restores_active_status() -> None:
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorReactivated",
        {"actor_id": str(_ACTOR_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    sql = conn.execute.await_args.args[0]
    assert "status = 'active'" in sql
    assert conn.execute.await_args.args[1] == _ACTOR_ID


@pytest.mark.unit
async def test_actor_deactivated_updates_status() -> None:
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorDeactivated",
        {"actor_id": str(_ACTOR_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_access_actor_summary" in sql
    assert "status = 'deactivated'" in sql
    assert args.args[1] == _ACTOR_ID


@pytest.mark.unit
async def test_actor_profile_forgotten_rewrites_cached_name_to_tombstone() -> None:
    """Post-erasure: the projection rewrites the cached display name
    to the locked tombstone literal so list reads see the same
    surface `load_actor_display_name` would compose. Status / kind /
    created_at stay unchanged; only `name` flips."""
    from cora.access.aggregates.actor import DELETED_ACTOR_DISPLAY_NAME

    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorProfileForgotten",
        {"actor_id": str(_ACTOR_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_access_actor_summary" in sql
    assert "SET name = $2" in sql
    assert args.args[1] == _ACTOR_ID
    assert args.args[2] == DELETED_ACTOR_DISPLAY_NAME


@pytest.mark.unit
async def test_actor_profile_forgotten_apply_is_idempotent() -> None:
    """Applying the same ActorProfileForgotten twice runs the same
    UPDATE both times; Postgres semantics make the net effect
    equivalent to one call. Mirrors the V1/V2 registration
    idempotency contract."""
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorProfileForgotten",
        {"actor_id": str(_ACTOR_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)
    await proj.apply(event, conn)

    assert conn.execute.await_count == 2
    first_args = conn.execute.await_args_list[0].args
    second_args = conn.execute.await_args_list[1].args
    assert first_args == second_args


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    """SQL-side filter guarantees apply() never sees unsubscribed
    types. If a future projection author adds an event_type to the
    subscribed set without adding a match arm, the bare match falls
    through (no execute, no error). Surfaces as missing rows in the
    projection table — easier to debug than a silent return swallowed
    inside the projection."""
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})

    await proj.apply(event, conn)

    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_apply_is_idempotent_for_actor_registered_v2() -> None:
    """ON CONFLICT DO NOTHING means re-applying the same
    ActorRegisteredV2 event a second time runs the same SQL again,
    which Postgres handles as a no-op. The projection author doesn't
    need to track which events have been seen."""
    proj = ActorSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ActorRegisteredV2",
        {
            "actor_id": str(_ACTOR_ID),
            "occurred_at": _NOW.isoformat(),
            "kind": "human",
        },
    )

    await proj.apply(event, conn)
    await proj.apply(event, conn)

    assert conn.execute.await_count == 2
    # Both calls have identical args; Postgres ON CONFLICT semantics
    # make the net effect equivalent to one call.
    first_args = conn.execute.await_args_list[0].args
    second_args = conn.execute.await_args_list[1].args
    assert first_args == second_args
