"""The `ObserveSupplyStatus` command -- monitor-driven status observation.

Per [[project_supply_monitor_trigger_design]]: carries the four
adapter-supplied fields needed to record a sensor-driven Supply
transition.

  - `supply_id`: target Supply aggregate.
  - `new_status`: the status the adapter observed. The decider
    enforces FSM source-state allowlists per new_status AND fences
    Monitor out of `Recovering -> Available` + `Unknown -> Available`
    (operator-only per [[project_supply_design]] Anti-hooks).
  - `monitor_ref`: identifies the originating sensor / file / log
    (carried verbatim onto the emitted event for audit).
  - `monitor_source_id`: the stable `MonitorSourceId` UUID of the
    in-process adapter subscription that emitted the observation;
    threaded into the event payload's `triggered_by` field per
    [[project_fold_symmetry_design]]. Distinct from `monitor_ref`:
    `monitor_ref` is the human-readable "sensor identity" (PV name,
    file path) while `monitor_source_id` is the stable adapter
    subscription handle that survives sensor reconfigurations.
  - `reason`: free-text audit string per the existing Supply
    transition convention (1-500 chars after trim).

`observed_at` is NOT on the command: the handler injects it from
the Clock port at call time (cross-BC non-determinism principle).
The adapter's wall-clock at observation is captured on the
SUBSCRIPTION side, not threaded through the command surface.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.identity import MonitorSourceId
from cora.supply.aggregates.supply import MonitorRef, SupplyStatus


@dataclass(frozen=True)
class ObserveSupplyStatus:
    """Monitor-driven status observation from an in-process adapter."""

    supply_id: UUID
    new_status: SupplyStatus
    monitor_ref: MonitorRef
    monitor_source_id: MonitorSourceId
    reason: str
