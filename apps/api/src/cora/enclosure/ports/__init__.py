"""Enclosure BC ports (BC-tier Protocols owned by Enclosure).

`EnclosureObserver` ships here per [[project_enclosure_stage1_design]]:
the inbound Monitor-trigger surface that streams permit-status
observations from substrate (PSS hardware contacts, EPICS PVs, P4P
subscriptions, Tango attributes) into the `observe_enclosure_status`
slice. SIL-rated hardware is ground truth; the port is the seam
between substrate observability and the CORA-owned permit FSM.

BC-tier port location per [[project_adapter_naming_design]]: stays
here until rule-of-three promotes to `cora.infrastructure.ports`.
Cross-BC `EnclosureLookup` (read-side, consumed by other BCs) has
landed at `cora.infrastructure.ports.enclosure_lookup` per the cross-BC
lookup home convention; consumers today are `run/start_run` and
`operation/start_procedure`.
"""

from cora.enclosure.ports.enclosure_observer import (
    AlwaysPermittedEnclosureObserver,
    EnclosureObservation,
    EnclosureObserver,
    EnclosureObserverScope,
)

__all__ = [
    "AlwaysPermittedEnclosureObserver",
    "EnclosureObservation",
    "EnclosureObserver",
    "EnclosureObserverScope",
]
