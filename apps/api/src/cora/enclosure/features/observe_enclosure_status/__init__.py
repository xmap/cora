"""Monitor-driven Enclosure permit-status observation (in-process inbound port).

Per [[project_enclosure_stage1_design]]: the `observe_enclosure_status`
slice is the Enclosure BC's inbound port for substrate-driven permit
transitions. Called by in-process adapters (the future EPICS / P4P /
Tango interlock subscriber per 2-BM Audit C, any future facility-bridge)
to flip an Enclosure's permit status without operator intervention. The
SIL-rated hardware interlock is ground truth; the slice carries each
observation as an `EnclosurePermitObserved` event with `trigger="Monitor"`
and a `monitor_ref` audit field identifying the source.

Per the design lock (D6.L2): NO REST route, NO MCP tool. Operators have
buttons; machines have ports. The Permitted target is reachable ONLY via
Monitor-driven observation; the decider rejects `trigger=Operator` at the
command-tier guard. Adapters call this slice directly via
`EnclosureHandlers.observe_enclosure_status(...)`.
"""

from cora.enclosure.features.observe_enclosure_status import tool
from cora.enclosure.features.observe_enclosure_status.command import (
    ObserveEnclosureStatus,
)
from cora.enclosure.features.observe_enclosure_status.decider import decide
from cora.enclosure.features.observe_enclosure_status.handler import Handler, bind
from cora.enclosure.features.observe_enclosure_status.route import router

__all__ = [
    "Handler",
    "ObserveEnclosureStatus",
    "bind",
    "decide",
    "router",
    "tool",
]
