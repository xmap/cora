"""Pure decider for the `ObserveEnclosureStatus` command.

Routes a Monitor-driven permit-status observation to the single
permit-axis transition event `EnclosurePermitObserved`. The decider
enforces `trigger == "Monitor"` as a command-tier guard; the typed
`monitor_source_id: MonitorSourceId` on the command structurally
prevents an operator from supplying a non-Monitor attribution at
the type level. Together they close the operator-assert-Permitted
backdoor per [[project_enclosure_stage1_design]] D6.L2 observation-
axis-only anti-lock.

Per L-EV-2 status-change-only: identical-status observations
(`state.permit_status == command.new_status`) return `[]` rather
than emitting a redundant event. This is the load-bearing
divergence from the Supply `observe_supply_status` precedent
(Supply treats identical-status as a guard violation; Enclosure
absorbs it silently).

## Validation order

1. State must not be None -> `EnclosureNotFoundError`.
2. Trigger must be `"Monitor"` -> `MonitorTriggerNotPermittedError`
   (D6.L2 command-tier guard; fires before lifecycle check so
   operator-asserted attempts on Decommissioned enclosures still
   surface as 400 not 409).
3. Lifecycle must be `Active` ->
   `EnclosureCannotObserveWhileDecommissionedError` when the
   enclosure has been decommissioned (terminal lifecycle).
4. Same-status short-circuit: `state.permit_status ==
   command.new_status` returns `[]` (L-EV-2).
5. Reason validation via `EnclosureReason` VO ->
   `InvalidEnclosureReasonError`.
"""

from datetime import datetime

from cora.enclosure.aggregates._value_types import EnclosureReason
from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureCannotObserveWhileDecommissionedError,
    EnclosureLifecycle,
    EnclosureNotFoundError,
    EnclosurePermitObserved,
    MonitorTriggerNotPermittedError,
)
from cora.enclosure.features.observe_enclosure_status.command import (
    ObserveEnclosureStatus,
)
from cora.shared.identity import MonitorSourceId

_TRIGGER_MONITOR = "Monitor"


def decide(
    state: Enclosure | None,
    command: ObserveEnclosureStatus,
    *,
    now: datetime,
    triggered_by: MonitorSourceId,
) -> list[EnclosurePermitObserved]:
    """Decide the events produced by a Monitor-driven permit observation.

    Invariants:
      - State must not be None -> EnclosureNotFoundError
      - Trigger must be 'Monitor' -> MonitorTriggerNotPermittedError
        (D6.L2 command-tier guard)
      - Lifecycle must be Active ->
        EnclosureCannotObserveWhileDecommissionedError
      - Identical-status observations return [] (L-EV-2 status-
        change-only; no event emitted)
      - Reason must be valid -> InvalidEnclosureReasonError

    `triggered_by` is the `MonitorSourceId` of the in-process adapter
    (EPICS PV listener, PSS substream subscriber, file watcher)
    whose observation produced this command. Pairs with
    trigger='Monitor' on the emitted event payload per
    [[project_fold_symmetry_design]].
    """
    if state is None:
        raise EnclosureNotFoundError(command.enclosure_id)

    if command.trigger != _TRIGGER_MONITOR:
        raise MonitorTriggerNotPermittedError(state.id, command.trigger)

    if state.lifecycle is EnclosureLifecycle.DECOMMISSIONED:
        raise EnclosureCannotObserveWhileDecommissionedError(state.id, state.lifecycle)

    if state.permit_status is command.new_status:
        return []

    reason = EnclosureReason(command.reason)
    monitor_ref_str = f"{command.monitor_ref.source_kind}:{command.monitor_ref.source_id}"

    return [
        EnclosurePermitObserved(
            enclosure_id=state.id,
            from_status=state.permit_status.value,
            to_status=command.new_status.value,
            reason=reason.value,
            trigger=_TRIGGER_MONITOR,
            triggered_by=triggered_by,
            occurred_at=now,
            monitor_ref=monitor_ref_str,
        )
    ]
