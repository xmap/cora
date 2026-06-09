"""Vertical slice for the `DecommissionEnclosure` command.

Module-as-namespace surface, symmetric with `register_enclosure`:

    from cora.enclosure.features import decommission_enclosure

    cmd = decommission_enclosure.DecommissionEnclosure(
        enclosure_id=enclosure_id,
        reason="end-of-life",
    )
    handler = decommission_enclosure.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Terminal transition (Active -> Decommissioned); strict-not-idempotent
per the decommission_facility precedent. Single-stream write;
`permit_status` is preserved as audit trail (no mutation on the
terminal transition).
"""

from cora.enclosure.features.decommission_enclosure import tool
from cora.enclosure.features.decommission_enclosure.command import DecommissionEnclosure
from cora.enclosure.features.decommission_enclosure.decider import decide
from cora.enclosure.features.decommission_enclosure.handler import Handler, bind
from cora.enclosure.features.decommission_enclosure.route import router

__all__ = [
    "DecommissionEnclosure",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
