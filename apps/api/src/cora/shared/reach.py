"""ReachTier: how CORA reached a substrate for one observation.

Originated in the Enclosure BC's permit-probe trail
([[project_enclosure_permit_probe_design]]) and hoisted here once a
second BC (Run, for the capture-observe seam) needed the same
vocabulary. `cora.run` cannot depend on `cora.enclosure.aggregates`
(tach), and the concept is substrate-neutral: it grades CORA's own
reach to whatever it is watching, never the thing being watched.
`cora.shared` has no dependencies of its own, so any BC may use this
without adding a cross-BC edge.
"""

from enum import StrEnum


class ReachTier(StrEnum):
    """How CORA reached a substrate for one observation.

    Two values ship. `RELAYED` means CORA received or fetched a value
    through the configured channel; `UNREACHED` means it could not,
    this tick. A stronger tier for a confirmed direct round trip to
    the authoritative source (as opposed to an intermediary, such as
    an EPICS CA gateway that may answer from its own cache) is
    deliberately NOT defined here: no producer in this codebase can
    currently prove one, and an unearned strong claim is worse than
    none. Adding a value later needs no migration in a consumer whose
    column is a length-CHECK rather than a value-enumerating CHECK.
    """

    RELAYED = "Relayed"
    UNREACHED = "Unreached"


__all__ = ["ReachTier"]
