"""End-to-end PG race test for `supersede_caution`'s multi-stream OCC.

Pins the cross-aggregate ConcurrencyError path on the Caution
parent-stream side: two supersede attempts both claiming the same
stale parent_version MUST result in one success + one
ConcurrencyError (the parent stream's version moved after the
first commit; the second batch's expected_version is now stale).

Closes Watch #14 from project_caution_design.md (concurrent-
supersede race) + bundles with the Campaign add_run race tests in
test_add_run_to_campaign_postgres.py.

Implementation note: this test bypasses the handler's load step
and constructs the two append_streams batches directly because
asyncio.gather under shared-pool serialization (the only
contention asyncpg single-pool gives us in-process) does not
reliably reproduce the version conflict; the handler always
reloads the parent before deciding. The race we actually care
about is the cross-process / multi-worker version-clash, which we
simulate here by pre-capturing the stale version once and
deliberately reusing it.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionRegistered,
    CautionSeverity,
    CautionSuperseded,
)
from cora.caution.aggregates.caution import (
    event_type_name as caution_event_type_name,
)
from cora.caution.aggregates.caution import (
    to_payload as caution_to_payload,
)
from cora.caution.features import register_caution
from cora.caution.features.register_caution.command import RegisterCaution
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import ConcurrencyError, StreamAppend
from cora.shared.identity import ActorId
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000001")
_AUTHOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000002"))
_CORRELATION_ID = UUID("00000000-0000-0000-0000-00000000c001")


@pytest.mark.integration
async def test_forced_concurrent_supersede_caution_raises_concurrency_error(
    db_pool: asyncpg.Pool,
) -> None:
    """Two supersede batches claiming the same stale parent_version on
    the Caution parent stream. First commits; second MUST
    ConcurrencyError. Pins the multi-stream OCC invariant for the
    Caution BC supersede path (mirror of the Campaign add_run forced-
    conflict test).
    """
    parent_id = uuid4()
    asset_id = uuid4()
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[parent_id, uuid4()],
    )

    # Register parent Caution (lands Active per 11b-a design).
    # authored_by is derived from principal_id at the handler
    # per 11b cleanup N9 (no spoofing surface); use _AUTHOR_ID as the
    # principal so the resulting event carries it.
    await register_caution.bind(deps)(
        RegisterCaution(
            target=AssetTarget(asset_id=asset_id),
            category=CautionCategory.WEAR,
            severity=CautionSeverity.CAUTION,
            text="hexapod stalls below 0.5 mm/s",
            workaround="run at 0.6 mm/s",
            tags=frozenset[str](),
        ),
        principal_id=_AUTHOR_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Capture stale parent version. Both supersede batches will claim
    # this value as their expected_version on the parent's stream.
    _, stale_parent_version = await deps.event_store.load("Caution", parent_id)

    child_a_id = uuid4()
    child_b_id = uuid4()

    def _build_supersede_batch(child_id: UUID) -> list[StreamAppend]:
        parent_event = CautionSuperseded(
            caution_id=parent_id,
            superseded_by_caution_id=child_id,
            occurred_at=_NOW,
        )
        child_event = CautionRegistered(
            caution_id=child_id,
            target=AssetTarget(asset_id=asset_id),
            category=CautionCategory.WEAR.value,
            severity=CautionSeverity.CAUTION.value,
            text="hexapod stalls below 0.6 mm/s (revised)",
            workaround="run at 0.7 mm/s",
            tags=frozenset[str](),
            authored_by=_AUTHOR_ID,
            expires_at=None,
            propagate_to_children=False,
            parent_id=parent_id,
            occurred_at=_NOW,
        )
        return [
            StreamAppend(
                stream_type="Caution",
                stream_id=parent_id,
                expected_version=stale_parent_version,
                events=[
                    to_new_event(
                        event_type=caution_event_type_name(parent_event),
                        payload=caution_to_payload(parent_event),
                        occurred_at=parent_event.occurred_at,
                        event_id=uuid4(),
                        command_name="SupersedeCaution",
                        correlation_id=_CORRELATION_ID,
                        principal_id=_PRINCIPAL_ID,
                    )
                ],
            ),
            StreamAppend(
                stream_type="Caution",
                stream_id=child_id,
                expected_version=0,
                events=[
                    to_new_event(
                        event_type=caution_event_type_name(child_event),
                        payload=caution_to_payload(child_event),
                        occurred_at=child_event.occurred_at,
                        event_id=uuid4(),
                        command_name="SupersedeCaution",
                        correlation_id=_CORRELATION_ID,
                        principal_id=_PRINCIPAL_ID,
                    )
                ],
            ),
        ]

    # First commit: succeeds. Parent stream goes stale -> stale+1.
    await deps.event_store.append_streams(_build_supersede_batch(child_a_id))

    # Second commit: still claims stale_parent_version on the parent
    # stream. Multi-stream OCC MUST raise ConcurrencyError; child_b's
    # stream is rolled back atomically (never gets the genesis event).
    with pytest.raises(ConcurrencyError) as exc_info:
        await deps.event_store.append_streams(_build_supersede_batch(child_b_id))

    assert exc_info.value.stream_type == "Caution"
    assert exc_info.value.stream_id == parent_id
    assert exc_info.value.expected == stale_parent_version
    assert exc_info.value.actual == stale_parent_version + 1

    # End-state: parent has exactly one CautionSuperseded event
    # (pointing to child_a, NOT child_b). Child_b's stream was rolled
    # back atomically and has zero events.
    parent_events, _ = await deps.event_store.load("Caution", parent_id)
    superseded_targets = [
        UUID(e.payload["superseded_by_caution_id"])
        for e in parent_events
        if e.event_type == "CautionSuperseded"
    ]
    assert superseded_targets == [child_a_id], (
        "Parent must point to child_a only; the failing batch's parent event must have rolled back."
    )

    child_b_events, child_b_version = await deps.event_store.load("Caution", child_b_id)
    assert child_b_events == [], (
        "Failing batch must NOT have committed to child_b's stream (atomic rollback)"
    )
    assert child_b_version == 0
