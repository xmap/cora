"""The `ObserveEnclosureStatus` command, monitor-driven permit observation.

Per [[project_enclosure_stage1_design]]: carries the adapter-supplied
fields needed to record a sensor-driven Enclosure permit transition.

  - `enclosure_id`: target Enclosure aggregate.
  - `new_status`: the `EnclosurePermitStatus` value the adapter
    observed (typed enum). The decider routes by parsed value and
    enforces the closed permit-status set (`Permitted | NotPermitted
    | Unknown`) as a defensive trailing guard against raw-payload
    bypasses.
  - `reason`: free-text audit string validated at the decider via the
    `EnclosureReason` VO (1-500 chars after trim) per the existing
    Enclosure transition convention.
  - `monitor_source_id`: the stable `MonitorSourceId` UUID of the
    in-process adapter subscription that emitted the observation,
    threaded into the emitted event payload's `triggered_by` field
    per [[project_fold_symmetry_design]].
  - `monitor_ref`: the typed `MonitorRef` VO carrying `source_kind` +
    `source_id` as separate components. The decider joins them into
    a colon-delimited wire string `{source_kind}:{source_id}` on the
    emitted `EnclosurePermitObserved` payload. Typed (NOT bare str)
    so adapter wiring is type-safe at the port-to-command boundary.
  - `trigger`: command-tier guard string. The decider rejects any
    value other than the literal `"Monitor"` with
    `MonitorTriggerNotPermittedError`, closing the
    operator-assert-Permitted backdoor (D6.L2 anti-lock; no operator
    path to `Permitted`). The defensive guard fences a programmer
    mistake in a custom adapter or test fixture; the type system
    enforces structural absence of operator-trigger semantics by
    typing `monitor_source_id` as `MonitorSourceId`.

`observed_at` is NOT on the command: the handler injects it from the
Clock port at call time (cross-BC non-determinism principle). The
adapter's wall-clock at observation crosses the seam on the
`EnclosureObservation` envelope at the port surface, not through the
command.
"""

from dataclasses import dataclass

from cora.enclosure.aggregates._value_types import MonitorRef
from cora.enclosure.aggregates.enclosure import EnclosureId, EnclosurePermitStatus
from cora.shared.identity import MonitorSourceId


@dataclass(frozen=True)
class ObserveEnclosureStatus:
    """Monitor-driven permit-status observation from an in-process adapter."""

    enclosure_id: EnclosureId
    new_status: EnclosurePermitStatus
    reason: str
    monitor_source_id: MonitorSourceId
    monitor_ref: MonitorRef
    trigger: str
