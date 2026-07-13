"""Evolver: replay events to reconstruct Allocation state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `AllocationEvent` without a matching match arm here.

Status mapping per event type:

  - `AllocationGranted`        -> GRANTED (genesis; sets
                                  `granted_at` + `granted_by`)
  - `AllocationActivated`      -> ACTIVE (single-source: Granted;
                                  sets `activated_at` +
                                  `activated_by`, the spend-window
                                  start)
  - `AllocationCeilingAmended` -> no status change (source: Granted |
                                  Active; overwrites `ceiling_usd`,
                                  PUT semantics)
  - `AllocationSealed`         -> SEALED (single-source: Active; sets
                                  `sealed_at` + `sealed_by` +
                                  `spent_usd_at_seal` + optional
                                  `end_reason`)
  - `AllocationVoided`         -> VOIDED (source: Granted | Active;
                                  sets `end_reason`)

Source-state guards live at the deciders, NOT here; the evolver
trusts the event log (folded events have already passed their
decider).

Transition arms use `dataclasses.replace`, which carries every
untouched field forward by construction, so the silent-wipe bug
class the Agent evolver guards against field-by-field cannot occur
here.

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.budget.aggregates.allocation.events import (
    AllocationActivated,
    AllocationCeilingAmended,
    AllocationEvent,
    AllocationGranted,
    AllocationSealed,
    AllocationVoided,
)
from cora.budget.aggregates.allocation.state import (
    Allocation,
    AllocationNote,
    AllocationStatus,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Allocation | None, event: AllocationEvent) -> Allocation:
    """Apply one event to the current state."""
    match event:
        case AllocationGranted(
            allocation_id=allocation_id,
            ceiling_usd=ceiling_usd,
            campaign_id=campaign_id,
            note=note,
            granted_by=granted_by,
            occurred_at=occurred_at,
        ):
            _ = state  # AllocationGranted is the genesis event; prior state ignored
            return Allocation(
                id=allocation_id,
                ceiling_usd=ceiling_usd,
                note=AllocationNote(note),
                campaign_id=campaign_id,
                granted_at=occurred_at,
                granted_by=granted_by,
                status=AllocationStatus.GRANTED,
            )
        case AllocationActivated(activated_by=activated_by, occurred_at=occurred_at):
            prior = require_state(state, "AllocationActivated")
            return replace(
                prior,
                status=AllocationStatus.ACTIVE,
                activated_at=occurred_at,
                activated_by=activated_by,
            )
        case AllocationCeilingAmended(ceiling_usd=ceiling_usd):
            prior = require_state(state, "AllocationCeilingAmended")
            return replace(prior, ceiling_usd=ceiling_usd)
        case AllocationSealed(
            spent_usd=spent_usd,
            reason=reason,
            sealed_by=sealed_by,
            occurred_at=occurred_at,
        ):
            prior = require_state(state, "AllocationSealed")
            return replace(
                prior,
                status=AllocationStatus.SEALED,
                sealed_at=occurred_at,
                sealed_by=sealed_by,
                spent_usd_at_seal=spent_usd,
                end_reason=reason,
            )
        case AllocationVoided(reason=reason):
            prior = require_state(state, "AllocationVoided")
            return replace(
                prior,
                status=AllocationStatus.VOIDED,
                end_reason=reason,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[AllocationEvent]) -> Allocation | None:
    """Replay a stream of events from the empty initial state."""
    state: Allocation | None = None
    for event in events:
        state = evolve(state, event)
    return state
