"""Evolver: replay events to reconstruct Enclosure state.

Three-event stream per the locked design:

  - `EnclosureRegistered`: genesis. Seeds `permit_status=UNKNOWN` and
    `lifecycle=ACTIVE` from the event TYPE, not from the genesis
    payload (L-state-1 Slim Aggregate rule). Folds `occurred_at` ->
    `registered_at` and `registered_by` denorm per
    [[project_fold_symmetry_design]] genesis pair.
  - `EnclosurePermitObserved`: operational-axis mutation. Replaces
    `permit_status` with `EnclosurePermitStatus(to_status)`. The
    monitor/reason envelope is NOT folded to state (envelope lives
    on the event log and projection-tier only, per L-state-7). Per
    L-EV-2 the handler short-circuits when `from_status==to_status`
    so this arm typically receives only true state changes; the
    evolver remains correct even if a same-status event is replayed.
  - `EnclosureDecommissioned`: structural-axis terminal. Sets
    `lifecycle=DECOMMISSIONED` and folds `occurred_at` ->
    `decommissioned_at` and `triggered_by` -> `decommissioned_by`
    per fold-symmetry terminal-transition pair. `permit_status` is
    preserved as audit trail (last observation before decommission).

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider). The
terminal `assert_never` case forces pyright (and the runtime) to error
if a new event type is added to `EnclosureEvent` without a matching
match arm here.

Each non-genesis arm explicitly forwards EVERY prior field via the
`Enclosure(...)` constructor (NOT `dataclasses.replace`) per the locked design
silent-wipe risk warning: if a new state field is added, this file
fails to type-check rather than silently dropping the field. Supply
evolver precedent.

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure.events import (
    EnclosureDecommissioned,
    EnclosureEvent,
    EnclosurePermitObserved,
    EnclosureRegistered,
)
from cora.enclosure.aggregates.enclosure.state import (
    Enclosure,
    EnclosureLifecycle,
    EnclosureName,
    EnclosurePermitStatus,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Enclosure | None, event: EnclosureEvent) -> Enclosure:
    """Apply one event to the current state."""
    match event:
        case EnclosureRegistered(
            enclosure_id=enclosure_id,
            name=name,
            containing_asset_id=containing_asset_id,
            registered_by=registered_by,
            occurred_at=occurred_at,
        ):
            _ = state  # EnclosureRegistered is the genesis event; prior state ignored
            return Enclosure(
                id=EnclosureId(enclosure_id),
                name=EnclosureName(name),
                containing_asset_id=containing_asset_id,
                permit_status=EnclosurePermitStatus.UNKNOWN,
                lifecycle=EnclosureLifecycle.ACTIVE,
                registered_at=occurred_at,
                registered_by=registered_by,
                decommissioned_at=None,
                decommissioned_by=None,
            )
        case EnclosurePermitObserved(to_status=to_status):
            prior = require_state(state, "EnclosurePermitObserved")
            return Enclosure(
                id=prior.id,
                name=prior.name,
                containing_asset_id=prior.containing_asset_id,
                permit_status=EnclosurePermitStatus(to_status),
                lifecycle=prior.lifecycle,
                registered_at=prior.registered_at,
                registered_by=prior.registered_by,
                decommissioned_at=prior.decommissioned_at,
                decommissioned_by=prior.decommissioned_by,
            )
        case EnclosureDecommissioned(
            triggered_by=triggered_by,
            occurred_at=occurred_at,
        ):
            prior = require_state(state, "EnclosureDecommissioned")
            return Enclosure(
                id=prior.id,
                name=prior.name,
                containing_asset_id=prior.containing_asset_id,
                permit_status=prior.permit_status,
                lifecycle=EnclosureLifecycle.DECOMMISSIONED,
                registered_at=prior.registered_at,
                registered_by=prior.registered_by,
                decommissioned_at=occurred_at,
                decommissioned_by=triggered_by,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[EnclosureEvent]) -> Enclosure | None:
    """Replay a stream of events from the empty initial state."""
    state: Enclosure | None = None
    for event in events:
        state = evolve(state, event)
    return state
