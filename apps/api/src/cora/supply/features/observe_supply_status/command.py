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

`observed_at` is NOT on the command: the handler stamps the event
from the Clock port at call time (cross-BC non-determinism
principle), so the recorded event carries CORA's ingest time.

An earlier version of this docstring said the substrate's own
observation time was "captured on the SUBSCRIPTION side". There is
no subscription side: `cora/supply/adapters` holds only
`postgres_supply_lookup`, with no observer port and no monitor, so
every `ObserveSupplyStatus` today comes from a caller that already
has the fact in hand. When a Supply monitor does land it inherits the
Enclosure shape, where the substrate time arrives as
`datetime | None` because equipment that reports a value without
stamping it is ordinary rather than broken. See
[[project-source-timestamp-design]].
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
