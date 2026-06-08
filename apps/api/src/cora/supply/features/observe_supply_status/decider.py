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

## Validation order

1. State must not be None -> `SupplyNotFoundError`.
2. Target transition (state.status -> command.new_status) must be
   Monitor-permitted -> `MonitorTriggerNotPermittedError` for the
   two operator-only target transitions; `SupplyCannot<Verb>Error`
   for source-state-disallowed transitions (mirrors the
   operator-driven decider checks).
3. Reason validation via `SupplyReason` VO -> `InvalidSupplyReasonError`.
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
_MONITOR_FORBIDDEN_TARGETS: frozenset[SupplyStatus] = frozenset(
    {SupplyStatus.AVAILABLE, SupplyStatus.DECOMMISSIONED}
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

    # UNKNOWN is reachable only via genesis (SupplyRegistered), never
    # via a Monitor transition. Defensive guard.
    raise MonitorTriggerNotPermittedError(state.id, command.new_status, state.status)
