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

`observed_at` is NOT on the command. The handler stamps the event
from the Clock port at call time (cross-BC non-determinism
principle), so what the recorded event carries is CORA's ingest
time.

  - `observed_at`: the SUBSTRATE's own time for the reading, or None
    when it reported none. Adapter-supplied data riding the command,
    which is not a non-determinism violation: the Clock still supplies
    `now` in the handler, and the decider computes neither. Deliberately
    has NO default, so every construction site must state what the
    substrate said, including saying None. A default is precisely how
    a field gets silently dropped at one hop of four.

Two clocks, and the distinction is the whole point of carrying both.
`observed_at` is when the substrate says it read the value;
`occurred_at`, stamped from the Clock port in the handler, is when
CORA learned of it. At APS 2-BM they are far apart: both PSS permit
PVs report no time at all, so `observed_at` is None for every real
reading there while `occurred_at` is always present.
"""

from dataclasses import dataclass
from datetime import datetime

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
    observed_at: datetime | None
