"""Pure decider for the `ObserveSupplyStatus` command.

Routes to the appropriate transition event class based on
`command.new_status`, enforcing both the FSM source-state allowlist
(same rules as the operator-driven transition slices) and the
Monitor-specific exclusions: `Recovering -> Available` and
`Unknown -> Available` are operator-only per
[[project_supply_design]] Anti-hooks (latched-alarm + first-
observation declaration semantics) and raise
`MonitorTriggerNotPermittedError` rather than producing an event.

Per [[project_supply_monitor_trigger_design]]: the emitted event
carries `trigger=TriggerSource.MONITOR.value` and serializes the
`monitor_ref` as `"{source_kind}:{source_id}"` on the event
payload for downstream audit ("which sensor said so").

## Status-change-only, unlike the operator-driven siblings

An observation whose `new_status` already equals the current status
returns `[]` and emits nothing. This deliberately DIVERGES from the
operator-driven sibling slices, which are strict-not-idempotent and
raise `SupplyCannot<Verb>Error` when re-asserting a status the Supply
already holds.

The divergence is the point. A monitor re-reporting a fact that is
still true is normal traffic, not an operator's mistake: a latched
substrate signal re-asserts on every reconnect and on every resend,
and the first real consumer (BLEPS, [[project_bleps_ingest_design]])
latches by design and clears asynchronously. Under the strict contract
the runtime would raise continuously in exactly the conditions the
feature exists to record.

The guard lives HERE and not in the runtime loop because "no change
means no fact" is a domain judgment, and the pure core is where such
judgments belong; a loop that filtered would be the shell deciding
what counts as a change. Matches
`cora.enclosure.features.observe_enclosure_status.decider`, the
in-codebase monitor-trigger precedent, which returns `[]` on an
identical-status observation for the same reason.

Note the ordering consequence below: the Monitor-forbidden check runs
BEFORE the no-op check, so an observation of `Available` raises rather
than quietly no-opping when the Supply is already `Available`. An
adapter is never allowed to assert `Available`, and silently accepting
it in the one case where it happens to match would hide the bug.

## Validation order

1. State must not be None -> `SupplyNotFoundError`.
2. Target must be Monitor-permitted -> `MonitorTriggerNotPermittedError`
   for `Available` / `Decommissioned` / `Unknown` regardless of source.
3. Unchanged status -> `[]`, no event (status-change-only, above).
4. Source-state allowlist per target -> `SupplyCannot<Verb>Error`
   (mirrors the operator-driven decider checks).
5. Reason validation via `SupplyReason` VO -> `InvalidSupplyReasonError`.
"""

from datetime import datetime

from cora.shared.identity import MonitorSourceId
from cora.supply.aggregates.supply import (
    MonitorTriggerNotPermittedError,
    Supply,
    SupplyCannotDegradeError,
    SupplyCannotMarkRecoveringError,
    SupplyCannotMarkUnavailableError,
    SupplyDegraded,
    SupplyMarkedRecovering,
    SupplyMarkedUnavailable,
    SupplyNotFoundError,
    SupplyReason,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.observe_supply_status.command import ObserveSupplyStatus

# Source-state allowlists per target status, mirroring the
# operator-driven sibling slice deciders verbatim. Centralized here
# because the new slice routes by new_status; the sibling deciders
# each hardcode their own target.
_DEGRADABLE_SOURCES: frozenset[SupplyStatus] = frozenset(
    {SupplyStatus.UNKNOWN, SupplyStatus.AVAILABLE, SupplyStatus.RECOVERING}
)
_UNAVAILABLE_SOURCES: frozenset[SupplyStatus] = frozenset(
    {
        SupplyStatus.UNKNOWN,
        SupplyStatus.AVAILABLE,
        SupplyStatus.DEGRADED,
        SupplyStatus.RECOVERING,
    }
)
_RECOVERING_SOURCES: frozenset[SupplyStatus] = frozenset({SupplyStatus.UNAVAILABLE})

# Monitor-forbidden target statuses. AVAILABLE is reachable via two
# operator-only transitions (Unknown -> Available via mark_supply_available;
# Recovering -> Available via restore_supply); fence both at decider
# level regardless of source. DECOMMISSIONED is operator-only because
# deregister_supply has no Monitor equivalent (no substream or timer
# should ever auto-decommission a Supply); see project_supply_design.
# UNKNOWN is genesis-only (set by the evolver from SupplyRegistered) and
# is listed HERE rather than relying on the fall-through guard at the
# bottom: the status-change-only check returns [] before that guard is
# reached, so an Unknown observation of an Unknown Supply would no-op
# silently instead of surfacing the adapter bug it is.
_MONITOR_FORBIDDEN_TARGETS: frozenset[SupplyStatus] = frozenset(
    {SupplyStatus.AVAILABLE, SupplyStatus.DECOMMISSIONED, SupplyStatus.UNKNOWN}
)


def decide(
    state: Supply | None,
    command: ObserveSupplyStatus,
    *,
    now: datetime,
    triggered_by: MonitorSourceId,
) -> list[SupplyDegraded | SupplyMarkedUnavailable | SupplyMarkedRecovering]:
    """Decide the events produced by a Monitor-driven status observation.

    Invariants:
      - State must not be None -> SupplyNotFoundError
      - new_status must be a Monitor-permitted target (not Available,
        not Decommissioned, not Unknown) -> MonitorTriggerNotPermittedError
      - new_status equal to the current status -> [] (no event;
        status-change-only, see the module docstring)
      - Source state must permit Degraded (Unknown / Available / Recovering)
        -> SupplyCannotDegradeError
      - Source state must permit Unavailable (not Unavailable)
        -> SupplyCannotMarkUnavailableError
      - Source state must permit Recovering (Unavailable only)
        -> SupplyCannotMarkRecoveringError
      - Reason must be valid -> InvalidSupplyReasonError

    `triggered_by` is the `MonitorSourceId` of the in-process adapter
    (substream subscriber, EPICS PV listener, file watcher) whose
    observation produced this command. Pairs with trigger="Monitor"
    on the emitted event payload per [[project_fold_symmetry_design]].
    """
    if state is None:
        raise SupplyNotFoundError(command.supply_id)

    if command.new_status in _MONITOR_FORBIDDEN_TARGETS:
        raise MonitorTriggerNotPermittedError(state.id, command.new_status, state.status)

    # Status-change-only: a monitor re-asserting a still-true fact is
    # normal traffic, not an error. Runs after the forbidden-target
    # check so an `Available` observation is still rejected loudly even
    # when it happens to match the current status.
    if command.new_status is state.status:
        return []

    reason = SupplyReason(command.reason)
    trigger = TriggerSource.MONITOR.value
    monitor_ref_str = f"{command.monitor_ref.source_kind}:{command.monitor_ref.source_id}"

    if command.new_status is SupplyStatus.DEGRADED:
        if state.status not in _DEGRADABLE_SOURCES:
            raise SupplyCannotDegradeError(state.id, state.status)
        return [
            SupplyDegraded(
                supply_id=state.id,
                from_status=state.status.value,
                reason=reason.value,
                trigger=trigger,
                triggered_by=triggered_by,
                occurred_at=now,
                monitor_ref=monitor_ref_str,
            )
        ]

    if command.new_status is SupplyStatus.UNAVAILABLE:
        if state.status not in _UNAVAILABLE_SOURCES:
            raise SupplyCannotMarkUnavailableError(state.id, state.status)
        return [
            SupplyMarkedUnavailable(
                supply_id=state.id,
                from_status=state.status.value,
                reason=reason.value,
                trigger=trigger,
                triggered_by=triggered_by,
                occurred_at=now,
                monitor_ref=monitor_ref_str,
            )
        ]

    if command.new_status is SupplyStatus.RECOVERING:
        if state.status not in _RECOVERING_SOURCES:
            raise SupplyCannotMarkRecoveringError(state.id, state.status)
        return [
            SupplyMarkedRecovering(
                supply_id=state.id,
                from_status=state.status.value,
                reason=reason.value,
                trigger=trigger,
                triggered_by=triggered_by,
                occurred_at=now,
                monitor_ref=monitor_ref_str,
            )
        ]

    # Unreachable today, and kept as enum-growth insurance: the forbidden
    # set plus the three handled targets exhaust `SupplyStatus`, so this
    # line only fires if a seventh member is added without a branch here.
    # It used to catch the UNKNOWN target, which now sits in the forbidden
    # set so the status-change-only return cannot swallow it.
    raise MonitorTriggerNotPermittedError(  # pragma: no cover
        state.id, command.new_status, state.status
    )
