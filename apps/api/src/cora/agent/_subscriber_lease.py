"""Cross-agent debrief lease primitive for Agent BC subscribers.

Per [[project-run-debriefer-lease-design]]: terminal-Run-event
side-effecting subscribers (`RunDebrieferSubscriber`,
`CautionDrafterSubscriber`, future agents) coordinate against
concurrent same-Run debriefs by appending a `DecisionDebriefRequested`
lease marker to the Run stream BEFORE invoking the LLM. The append
uses the Run aggregate's current `expected_version`; first writer
wins via the existing `UNIQUE(stream_type, stream_id, version)`
optimistic-concurrency primitive on the events table. Losing
subscribers see `ConcurrencyError`, identify the winning agent via
stream re-load, and exit without consuming LLM tokens.

The lease event_id is derived as
`uuid5(run_id, f"lease:{terminal_event_id}:{agent_id}")` so the same
agent's retries are idempotent (re-append fails on event_id UNIQUE)
but different agents compete on stream version.

Helper hoisted at first-use (RunDebriefer + CautionDrafter both ship
the pattern at the same time per design memo's rule-of-three
preemption for domain symmetry).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError
from cora.run.aggregates.run.events import DecisionDebriefRequested

if TYPE_CHECKING:
    from datetime import datetime

    from cora.infrastructure.ports.event_store import EventStore, StoredEvent

_log = get_logger(__name__)

_RUN_STREAM_TYPE = "Run"
_LEASE_EVENT_TYPE = DecisionDebriefRequested.__name__


def derive_lease_event_id(
    *,
    run_id: UUID,
    debriefer_agent_id: UUID,
    terminal_event_id: UUID,
) -> UUID:
    """Compute the deterministic lease event_id for a (run, agent, terminal-event) triple.

    Including `debriefer_agent_id` in the uuid5 seed means cross-agent
    contention plays out on stream version (different event_ids,
    different attempts to write at the same expected_version) rather
    than on event_id UNIQUE. Same-agent retries are idempotent: the
    re-append hits event_id UNIQUE and the helper treats the
    pre-existing lease as the previous successful attempt.
    """
    return uuid5(run_id, f"lease:{terminal_event_id}:{debriefer_agent_id}")


def _find_lease_winner_for_terminal_event(
    stored_events: list[StoredEvent],
    terminal_event_id: UUID,
) -> UUID | None:
    """Scan stored Run events for the lease winner for a terminal event.

    Returns the `debriefer_agent_id` of the first matching
    `DecisionDebriefRequested` event whose payload's
    `terminal_event_id` matches; None if no such event exists.
    First-match-from-head: in a well-formed stream, at most one lease
    per terminal event is ever appended successfully (the rest hit
    ConcurrencyError and never persist).
    """
    target = str(terminal_event_id)
    for event in stored_events:
        if event.event_type != _LEASE_EVENT_TYPE:
            continue
        if event.payload.get("terminal_event_id") != target:
            continue
        winner_raw = event.payload.get("debriefer_agent_id")
        if winner_raw is None:
            continue
        return UUID(winner_raw)
    return None


async def attempt_debrief_lease(
    event_store: EventStore,
    *,
    run_id: UUID,
    debriefer_agent_id: UUID,
    terminal_event: StoredEvent,
    occurred_at: datetime,
    command_name: str,
) -> tuple[bool, UUID | None]:
    """Try to acquire the debrief lease for one Run terminal event.

    Returns:
      - `(True, None)` when the lease was acquired (this agent should
        proceed to the LLM call + write its substantive Decision).
      - `(False, winner_agent_id)` when another agent already owns
        the lease for this terminal event (this agent should write a
        `DebriefConflicted` Decision and exit without an LLM call).
        `winner_agent_id` is None only on the rare case where the Run
        stream version advanced between load and append for a reason
        other than a competing lease (e.g., a late-arriving
        `RunAddedToCampaign` event); the subscriber treats this as a
        loss and exits without identifying a winner.

    Algorithm:
      1. Re-load Run stream (per Operation BC lazy-open pattern; the
         subscriber's earlier `load_run` snapshot may be stale).
      2. If a lease event for this `terminal_event_id` is already on
         the stream, return same-agent / cross-agent outcome based on
         the recorded `debriefer_agent_id`.
      3. Otherwise attempt to append the lease with the freshly-read
         `expected_version`. On `ConcurrencyError`, re-scan to
         identify the winner.

    Single-attempt: the race is one-shot in practice because terminal
    Run events are themselves terminal (no further Run-lifecycle
    events follow in normal operation). The only retry case worth
    handling would be a late-arriving non-lease Run event landing
    between this helper's load + append, which is rare and surfaces
    as `(False, None)` for the caller to log + exit.

    The lease event carries `causation_id = terminal_event.event_id`
    so the Run stream's audit trail links the lease back to the
    triggering terminal event. `principal_id` is the
    `debriefer_agent_id` (the Agent's identity-shared Actor.id).

    Emits structured log lines at every terminal branch:
      - `lease.acquired` on clean acquisition (append succeeded)
      - `lease.same_agent_replay` when initial scan returned own lease
        (crash-recovery / projection re-fire path)
      - `lease.lost` on any loss path; `winning_agent_id` field is
        the foreign agent id, or null when the version advanced for
        a non-lease reason (the degenerate `(False, None)` path).
      - `lease.conflict_on_append` precedes `lease.acquired` /
        `lease.lost` when the append raced and we re-scanned.

    The correlation_id is sourced from the terminal Run event so the
    lease lines join with the subscriber's `<subscriber>.start` /
    `<subscriber>.lease_lost` lines on the same log query.
    """
    lease_event_id = derive_lease_event_id(
        run_id=run_id,
        debriefer_agent_id=debriefer_agent_id,
        terminal_event_id=terminal_event.event_id,
    )

    log = _log.bind(
        run_id=str(run_id),
        terminal_event_id=str(terminal_event.event_id),
        debriefer_agent_id=str(debriefer_agent_id),
        correlation_id=str(terminal_event.correlation_id),
        command_name=command_name,
    )

    stored, current_version = await event_store.load(_RUN_STREAM_TYPE, run_id)

    winner = _find_lease_winner_for_terminal_event(stored, terminal_event.event_id)
    if winner is not None:
        if winner == debriefer_agent_id:
            log.info("lease.same_agent_replay", current_version=current_version)
            return True, None
        log.info(
            "lease.lost",
            winning_agent_id=str(winner),
            decided_by="initial_scan",
            current_version=current_version,
        )
        return False, winner

    lease_envelope = to_new_event(
        event_type=_LEASE_EVENT_TYPE,
        payload={
            "run_id": str(run_id),
            "debriefer_agent_id": str(debriefer_agent_id),
            "terminal_event_id": str(terminal_event.event_id),
            "occurred_at": occurred_at.isoformat(),
        },
        occurred_at=occurred_at,
        event_id=lease_event_id,
        command_name=command_name,
        correlation_id=terminal_event.correlation_id,
        causation_id=terminal_event.event_id,
        principal_id=debriefer_agent_id,
    )

    try:
        await event_store.append(
            stream_type=_RUN_STREAM_TYPE,
            stream_id=run_id,
            expected_version=current_version,
            events=[lease_envelope],
        )
    except ConcurrencyError:
        log.info("lease.conflict_on_append", attempted_version=current_version)
        stored, post_version = await event_store.load(_RUN_STREAM_TYPE, run_id)
        winner = _find_lease_winner_for_terminal_event(stored, terminal_event.event_id)
        if winner == debriefer_agent_id:
            log.info(
                "lease.acquired", decided_by="post_conflict_rescan", current_version=post_version
            )
            return True, None
        log.info(
            "lease.lost",
            winning_agent_id=str(winner) if winner is not None else None,
            decided_by="post_conflict_rescan",
            current_version=post_version,
        )
        return False, winner

    log.info("lease.acquired", decided_by="append", current_version=current_version + 1)
    return True, None


__all__ = ["attempt_debrief_lease", "derive_lease_event_id"]
