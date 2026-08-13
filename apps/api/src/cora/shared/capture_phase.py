"""CapturePhase: the facility-neutral lifecycle phase of an observed capture.

Originated on the Run BC's `CaptureObserver` port and hoisted here for
the same reason `ReachTier` was: `cora.infrastructure` (where
`Settings.capture_status_phases` validates a deployment's declared
literal-to-phase mapping) cannot depend on `cora.run.ports` (tach: BCs
depend on infrastructure, never the reverse), so the one enum both
sides need to agree on has to live below both of them.
"""

from enum import StrEnum


class CapturePhase(StrEnum):
    """The facility-neutral lifecycle phase of an observed capture.

    Closed and small on purpose: this is the vocabulary CORA's spine
    reasons over, not the vocabulary any one facility's tool emits.
    `UNRECOGNIZED` is a first-class member, not an absence: a substrate
    literal that does not match the deployment's declared mapping
    reports `UNRECOGNIZED` rather than being coerced into a nearby
    phase or dropped silently, so a vocabulary drift (a tool upgrade
    that renames a status) is visible in the record rather than
    misread as routine progress.
    """

    BEGUN = "Begun"
    PROGRESSING = "Progressing"
    ENDED = "Ended"
    ABORTED = "Aborted"
    UNRECOGNIZED = "Unrecognized"


__all__ = ["CapturePhase"]
