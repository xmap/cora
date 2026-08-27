"""BeamRequirement: whether an execution needs beam to be meaningful.

Declared per execution and read by the beam-availability pre-flight in
both `start_run` and `start_procedure`, which is why it lives below both
BCs rather than in either one.

The gate those two deciders share refuses to start when the front-end or
station shutter is closed or the upstream FES permit is denied. That is
right for a measurement and wrong for two ordinary cases that were
blocked outright before this enum existed:

  - a dark-field capture, which is DEFINED by the absence of beam: its
    first step closes the shutter the gate insists be open, and
  - a maintenance task (a hexapod power-cycle, an IOC restart), which
    touches no beam at all.

And it is wrong for the window that matters most operationally. Beamline
time alternates between user operations and no-beam periods, and
commissioning can only happen in the second. A gate that refuses every
execution without beam therefore refuses every execution during the only
period commissioning is possible.

`REQUIRED` is the default everywhere. An execution that declares nothing
keeps the pre-existing behaviour exactly, so this enum widens what can be
expressed without changing what any existing caller does.

NOT A SAFETY CONTROL. The interlocks are the PSS (people) and BLEPS
(equipment); CORA reads both and writes to neither, and nothing here
changes that. The beam gate is an operational readiness check, so a
wrong `NOT_REQUIRED` yields an unusable measurement rather than a
hazard. It is also not silent: the deciders record the observed beam
state and the declared requirement on the start event either way, so the
record distinguishes "started with beam" from "started without beam
under a declared exemption" instead of collapsing them.
"""

from enum import StrEnum


class BeamRequirement(StrEnum):
    """Whether a Run or Procedure needs beam available to start.

    Deliberately two members. A third, "must NOT have beam", was
    considered for the dark-field case and rejected: a dark field is
    perfectly valid during a beamtime with beam up, because its own
    first step closes the shutter. Forbidding beam would break the
    ordinary in-beamtime path to describe a precondition the recipe
    already establishes for itself.
    """

    REQUIRED = "Required"
    """Beam must be available at start. The default, and the pre-flight
    behaves exactly as it did before this enum existed."""

    NOT_REQUIRED = "NotRequired"
    """Beam availability is irrelevant to this execution, so the gate
    does not refuse on it. The state is still read and still recorded."""


__all__ = ["BeamRequirement"]
