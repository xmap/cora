"""Storage-cardinality idempotency tests for `promote_caution_proposal`.

The existing contract test
`test_promote_caution_proposal_endpoint.test_post_promote_same_idempotency_key_replays_cached_caution_id`
asserts only that two POSTs with the same Idempotency-Key return
the same caution_id. A Brandur cache-miss regression (key cache
evicted between calls; second call writes fresh events but the
deterministic-id machinery returns the same caution_id) would not
be caught at that surface — only at the EVENT STREAM.

This module pins three storage-level invariants per call:

  1. **Event-row count**: exactly one CautionRegistered row on the
     resulting caution stream (register path) or exactly one
     CautionSuperseded on parent + one CautionRegistered on child
     (supersede path).
  2. **Idempotency-row count**: exactly one row in the
     `idempotency_keys` table for the (principal_id, command_hash, key)
     tuple.
  3. **Caller-observable response**: same caution_id returned.

Cross-stream invariant for the supersede path: both events share
the same originating transaction (no all-or-nothing partial state
where the parent flipped but the child stream is empty, or vice
versa). The handler's `EventStore.append_streams(...)` provides
this; the test asserts the visible row counts.

Companion: thundering-herd (concurrent identical-key) test left
as a follow-up: it needs an additional asyncio coordination
helper that the existing PG fixtures don't yet provide.

Sources for the test pattern: Brandur Leach's idempotency canon
(https://brandur.org/idempotency-keys) plus the storage-cardinality
gap-fill the post-review audit research called out.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingParameterType=false, reportPrivateUsage=false, reportUnknownParameterType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.features.promote_caution_proposal import PromoteCautionProposal
from cora.agent.seed_caution_drafter import (
    CAUTION_DRAFTER_AGENT_ID,
    seed_caution_drafter_agent,
)
from cora.agent.wire import wire_agent
from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionSeverity,
)
from cora.caution.features.register_caution import RegisterCaution
from cora.caution.features.register_caution import bind as bind_register_caution
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_CAUTION_PROPOSAL,
    DecisionConfidenceSource,
    DecisionRegistered,
)
from cora.decision.aggregates.decision import event_type_name as decision_event_type_name
from cora.decision.aggregates.decision import to_payload as decision_to_payload
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 17, 15, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000099c01")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000009900c")
_ASSET_ID = UUID("01900000-0000-7000-8000-000000000ccc")

_PROPOSED_CAUTION_NOTICE: dict[str, Any] = {
    "target_kind": "Asset",
    "target_id": str(_ASSET_ID),
    "category": "Wear",
    "severity": "Notice",
    "title": "Idempotency-test Caution",
    "body": (
        "Body for the idempotency cardinality test; spans enough characters "
        "to satisfy the schema minLength on body."
    ),
    "tags": ["idempotency-test"],
}


async def _seed_caution_proposal_decision(
    deps,
    *,
    decision_id: UUID,
    choice: str = "ProposeNotice",
    inputs: dict[str, Any] | None = None,
) -> None:
    """Append a CautionDrafter-authored CautionProposal Decision.

    Uses `CAUTION_DRAFTER_AGENT_ID` as `actor_id` so the provenance
    gate passes (the agent is seeded by callers via
    `seed_caution_drafter_agent`).
    """
    event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(CAUTION_DRAFTER_AGENT_ID),
        context=DECISION_CONTEXT_CAUTION_PROPOSAL,
        choice=choice,
        parent_id=None,
        override_kind=None,
        rule="agent:CautionDrafter:v1",
        reasoning=(
            "Idempotency-test rationale narrative spanning enough words to satisfy the bound."
        ),
        confidence=0.72,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        inputs=inputs if inputs is not None else {"proposed_caution": _PROPOSED_CAUTION_NOTICE},
        reasoning_signature=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=decision_event_type_name(event),
        payload=decision_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="CautionDrafterSubscriber",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=CAUTION_DRAFTER_AGENT_ID,
    )
    await deps.event_store.append(
        stream_type="Decision",
        stream_id=decision_id,
        expected_version=0,
        events=[new_event],
    )


async def _count_events_on_stream(
    db_pool: asyncpg.Pool, *, stream_type: str, stream_id: UUID
) -> int:
    """COUNT(*) on the events table for one aggregate stream."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*)::int AS n FROM events WHERE stream_type = $1 AND stream_id = $2",
            stream_type,
            stream_id,
        )
        assert row is not None
        return int(row["n"])


async def _count_events_of_type_on_stream(
    db_pool: asyncpg.Pool,
    *,
    stream_type: str,
    stream_id: UUID,
    event_type: str,
) -> int:
    """COUNT(*) filtered by event_type — useful on supersede parent stream
    where genesis + supersede coexist."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*)::int AS n FROM events "
            "WHERE stream_type = $1 AND stream_id = $2 AND event_type = $3",
            stream_type,
            stream_id,
            event_type,
        )
        assert row is not None
        return int(row["n"])


async def _count_idempotency_rows(db_pool: asyncpg.Pool, *, principal_id: UUID, key: str) -> int:
    """COUNT(*) on idempotency_keys for one (principal_id, key) pair.

    The Brandur envelope's row is keyed on (principal_id, key,
    command_hash), but for the same body the hash is constant —
    one row per call series.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*)::int AS n FROM idempotency_keys WHERE principal_id = $1 AND key = $2",
            principal_id,
            key,
        )
        assert row is not None
        return int(row["n"])


# ---------------------------------------------------------------------------
# Register-path: storage-cardinality on idempotent replay
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_promote_register_path_idempotency_storage_cardinality(
    db_pool: asyncpg.Pool,
) -> None:
    """Two replays of the same Idempotency-Key produce EXACTLY ONE
    CautionRegistered event on EXACTLY ONE caution stream PLUS
    EXACTLY ONE idempotency_keys row. Catches the Brandur cache-miss
    regression class where the response is replayed correctly but
    the underlying event stream is double-written."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(8)])
    await seed_caution_drafter_agent(deps)
    decision_id = uuid4()
    await _seed_caution_proposal_decision(deps, decision_id=decision_id)

    handler = wire_agent(deps).promote_caution_proposal
    idempotency_key = f"ck-promote-register-{uuid4().hex[:8]}"
    cmd = PromoteCautionProposal(decision_id=decision_id)

    # First call -> writes events + idempotency row + returns caution_id.
    caution_id_1 = await handler(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key=idempotency_key,
    )

    # Second call (same key, same body) -> Brandur envelope short-circuits;
    # nothing new should land on either the caution stream or the
    # idempotency table.
    caution_id_2 = await handler(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key=idempotency_key,
    )

    # Response-layer (existing assertion baseline).
    assert caution_id_1 == caution_id_2

    # Storage-layer cardinality — the load-bearing addition.
    event_count = await _count_events_on_stream(
        db_pool, stream_type="Caution", stream_id=caution_id_1
    )
    assert event_count == 1, (
        f"expected exactly 1 event on Caution stream {caution_id_1}, got "
        f"{event_count} (Brandur cache-miss regression?)"
    )

    idempotency_count = await _count_idempotency_rows(
        db_pool, principal_id=_PRINCIPAL_ID, key=idempotency_key
    )
    assert idempotency_count == 1, (
        f"expected exactly 1 idempotency_keys row for key {idempotency_key!r}, "
        f"got {idempotency_count}"
    )


# ---------------------------------------------------------------------------
# Supersede-path: storage-cardinality across both atomic-written streams
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_promote_supersede_path_idempotency_storage_cardinality(
    db_pool: asyncpg.Pool,
) -> None:
    """The supersede path writes TWO events atomically (parent
    Superseded + child Registered) via append_streams. On idempotent
    replay, exactly one of EACH event must remain — no double-flip
    on parent, no second child stream, exactly one envelope row."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(12)])
    await seed_caution_drafter_agent(deps)

    # First, register a parent Caution via Caution BC's slice.
    register = bind_register_caution(deps)
    parent_id = await register(
        RegisterCaution(
            target=AssetTarget(asset_id=_ASSET_ID),
            category=CautionCategory.WEAR,
            severity=CautionSeverity.NOTICE,
            text="prior caution from C.1 idempotency PG test",
            workaround="prior workaround narrative used during the C.1 test setup",
            tags=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Now seed a ProposeSupersede Decision pointing at it.
    proposed = dict(_PROPOSED_CAUTION_NOTICE)
    proposed["severity"] = "Caution"
    proposed["title"] = "Refined: encoder drift"
    proposed["supersedes_caution_id"] = str(parent_id)

    decision_id = uuid4()
    await _seed_caution_proposal_decision(
        deps,
        decision_id=decision_id,
        choice="ProposeSupersede",
        inputs={"proposed_caution": proposed},
    )

    handler = wire_agent(deps).promote_caution_proposal
    idempotency_key = f"ck-promote-supersede-{uuid4().hex[:8]}"
    cmd = PromoteCautionProposal(decision_id=decision_id)

    # First call writes both events; second is a cache hit.
    child_id_1 = await handler(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key=idempotency_key,
    )
    child_id_2 = await handler(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key=idempotency_key,
    )

    # Response-layer.
    assert child_id_1 == child_id_2

    # Parent stream: exactly genesis CautionRegistered + 1 CautionSuperseded.
    parent_total = await _count_events_on_stream(
        db_pool, stream_type="Caution", stream_id=parent_id
    )
    assert parent_total == 2, (
        f"parent caution stream should have exactly 2 events "
        f"(genesis + Superseded), got {parent_total}"
    )
    parent_superseded = await _count_events_of_type_on_stream(
        db_pool,
        stream_type="Caution",
        stream_id=parent_id,
        event_type="CautionSuperseded",
    )
    assert parent_superseded == 1, (
        f"parent caution should have flipped Superseded exactly once, got {parent_superseded}"
    )

    # Child stream: exactly 1 CautionRegistered.
    child_total = await _count_events_on_stream(
        db_pool, stream_type="Caution", stream_id=child_id_1
    )
    assert child_total == 1, (
        f"child caution stream should have exactly 1 CautionRegistered, got {child_total}"
    )

    # Idempotency row count.
    idempotency_count = await _count_idempotency_rows(
        db_pool, principal_id=_PRINCIPAL_ID, key=idempotency_key
    )
    assert idempotency_count == 1


# ---------------------------------------------------------------------------
# Negative pin: without the key, replays MUST write again.
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_promote_register_path_without_key_writes_distinct_streams(
    db_pool: asyncpg.Pool,
) -> None:
    """Negative pin: same Decision but NO idempotency key on either
    call → handler creates two DISTINCT Cautions (different ids,
    independent streams, two `events`-table rows total). Protects the
    contract that idempotency is opt-in via the header."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(8)])
    await seed_caution_drafter_agent(deps)
    decision_id = uuid4()
    await _seed_caution_proposal_decision(deps, decision_id=decision_id)

    handler = wire_agent(deps).promote_caution_proposal
    cmd = PromoteCautionProposal(decision_id=decision_id)

    caution_id_1 = await handler(cmd, principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)
    caution_id_2 = await handler(cmd, principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert caution_id_1 != caution_id_2
    assert (
        await _count_events_on_stream(db_pool, stream_type="Caution", stream_id=caution_id_1) == 1
    )
    assert (
        await _count_events_on_stream(db_pool, stream_type="Caution", stream_id=caution_id_2) == 1
    )
