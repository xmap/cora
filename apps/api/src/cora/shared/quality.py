"""Quality: how much a consumer may lean on one measured value.

The `Quality` enum lived in `cora.operation.ports.measurement` and is
hoisted here, beside `reach.py`, for the same two reasons that one was:
consumers outside the Operation BC read it (`cora.api`'s three observers,
the beam-availability lookup), and `cora.shared` has no dependencies of
its own, so any of them may use it without adding a cross-BC edge.
`measurement.py` re-exports it, so nothing that imports it from the port
had to change.

## Two questions, and picking the wrong one is invisible

The enum is a trichotomy, not a scale, and a consumer is choosing
between two genuinely different questions:

  - **Can I BELIEVE this value?** Only `Bad` says no. `Uncertain` is
    what a substrate reports when the value is fine but the PROCESS it
    describes is in alarm, which is a fact about the world rather than
    about the reading.
  - **Can I ACT on this value?** Then any annotation at all is a reason
    to stop, and only `Good` will do.

Both are legitimate. The enum's own docstring has said so, and asked
each use site to state which it means, since it was written. Sites did
state it, in the only vocabulary available: a raw comparison whose
meaning you can only recover by working out which way the polarity
falls. That is why the SAME defect shipped three times, in three
independently written consumers, each answering "can I believe" with the
test for "can I act":

  - the hutch permit (`S02BM-PSS:StaB:SecureM`), fixed 2026-08-09. The
    PSS raises MAJOR whenever the hutch is not secured, so a hutch CORA
    could plainly read reported `Unknown` forever.
  - the BLEPS interlock flags, fixed 2026-08-23. A BLEPS record raises
    MAJOR precisely when its flag asserts, so the strict floor did not
    discard SOME readings, it discarded exactly the tripped ones and
    kept the quiet ones. The observer could only ever see a healthy
    beamline.
  - the beam-availability gate, fixed here. Measured on arcturus
    2026-08-24: all three PVs carry `ZSV=MAJOR`, `OSV=NO_ALARM`, so
    state 0 alarms and state 1 is silent. On `BeamBlockingM`, whose
    polarity is INVERTED, state 0 is the shutter OPEN. So an open
    shutter was unreadable, a closed one readable and closed, and the
    gate could not pass in any state of the beamline.

One shape, three times, because three people each re-derived the
answer. That is the rule-of-three trigger, and this module is the
response: the two questions get names, so a call site declares which
one it is asking instead of encoding it in an operator.

`test_quality_floors_are_named` (architecture) keeps it that way by
refusing a raw comparison against a quality literal outside the
adapters that PRODUCE quality. It caught a fourth occurrence before it
ever ran against real hardware: `cora.operation.acquisitions`'s
detector-done poll (`_acquisition_finished`) had NO floor at all, so a
`Bad` reading whose stale value happened to decode to "Done" would have
recorded a capture as finished when the value meant nothing. Not
reachable at 2-BM (`CONTROL_WRITES_ENABLED=false`), so this one was
caught by review rather than by a facility, but it is the same question
answered the same way: the poll asks whether the detector reported Done,
not whether the read is clean enough to trust unconditionally, so the
floor is `believable`.

## The split is per QUESTION, not per component

`believable` and `actionable` are not "the observers' floor" and "the
Conductor's floor". The Conductor uses BOTH: a check step asks "can I
act on this measured value" (`actionable`), while the acquisitions
poll above asks "did the detector report Done" (`believable`), and
answering the second one with the first would make a detector carrying
an unrelated standing `Uncertain` alarm (a temperature warning, a
nearly-full file-writer disk) never readable as finished. Read the
QUESTION a call site is asking before reaching for either name; do not
infer it from which BC or module the call site lives in.

## Why an alarmed reading is safe to believe

Every believe-floor consumer here is either recording what a facility
interlock reported, or deciding when an ALREADY-ISSUED command (a
detector already told to acquire) has finished. Neither actuates
anything on the strength of the alarmed reading itself: the PSS holds
the hutch, BLEPS protects the equipment, ACIS holds the shutters, and
the detector was already commanded before its `Acquire_RBV` is ever
read. A designed MAJOR is the interlock (or the detector) doing its job
of putting a condition on an operator's screen, and treating that as
"unreadable" throws away exactly the readings most worth seeing.

`Bad` stays disqualifying on both floors, because it is the one value
that says the number itself is untrustworthy rather than the world
being interesting.
"""

from typing import Literal

Quality = Literal["Good", "Uncertain", "Bad"]
"""Closed 3-value quality enum matching OPC UA's spec-defined severity
grouping and the NAMUR / ISA-95 vocabulary.

Per the OPC UA sanity check in
[[project_control_port_generalization_research]], `StatusCode`'s top
2 bits are exactly this trichotomy:
`Good = 0b00 | Uncertain = 0b01 | Bad = 0b10`. EPICS's 4-value
severity collapses (`NO_ALARM -> Good`, `MINOR | MAJOR -> Uncertain`,
`INVALID -> Bad`): EPICS distinguishes a value that is fine while the
process it describes is in alarm (MINOR / MAJOR) from a value that
cannot be trusted at all (INVALID), and only the latter is Bad.
Tango's 5-value `AttrQuality` collapses (`VALID -> Good`,
`WARNING | CHANGING -> Uncertain`, `ALARM | INVALID -> Bad`).

Consumers choose their own floor against this enum, through
`believable` or `actionable` rather than by comparing to a literal.
Neither floor is the default; each use site names which it means.

Substrate-specific forensic detail (EPICS `alarm_status`, Tango
string detail, OPC UA's ~240 named sub-codes such as
`BadCommunicationError` / `UncertainDataSubNormal`) lands in
`Measurement.quality_detail` as an opaque string; the closed enum stays
tight.
"""


def believable(quality: Quality) -> bool:
    """Is this value worth reading at all? False only for `Bad`.

    The floor for a consumer asking "can I believe this reading", never
    "is this consumer passive": the permit observers, the BLEPS supply
    observer, the capture baseline reader, the beam-availability lookup,
    and (inside the Conductor, alongside `actionable` below for its OTHER
    decisions) the acquisitions detector-done poll.

    `Uncertain` passes, and that is the entire point rather than a
    concession. A facility annotates a signal precisely when the
    condition it reports is worth attention, so on an interlock the
    alarm IS the assertion, and on a detector readback an unrelated
    standing alarm says nothing about whether the value itself is
    trustworthy. A floor that rejected `Uncertain` here would be blind
    to exactly the readings that matter and clear-sighted about the
    boring ones, which is worse than blind: it looks like a healthy
    beamline, or a detector that never finishes.

    The loosening runs BOTH ways and a caller should know it: an
    alarmed reading can now open a gate, or end a poll, as well as
    close/continue one. See the module docstring's "safe to believe"
    section for why that is acceptable for every consumer of this floor.
    """
    return quality != "Bad"


def actionable(quality: Quality) -> bool:
    """Is this value clean enough to drive an automated act? `Good` only.

    The floor for a consumer asking "can I act on the strength of this
    number", never "which BC am I in": the Conductor's check steps and
    capture assertions, and the optimizer's observation inputs. The
    SAME Conductor also calls `believable` for its acquisitions poll
    (see that function), because that call is a different question, not
    a different component; see the module docstring's "per QUESTION, not
    per component" section before assuming one BC means one floor.

    Stricter than `believable` deliberately, and the difference is not
    caution for its own sake. A check step's job is to decide whether a
    procedure may continue; a `MINOR` on the value it is checking means
    the facility has flagged that reading, and continuing anyway is the
    machine overruling the flag. Recording the same reading, or reading
    back whether an already-issued command finished, is not that: it is
    not a NEW act taken on the strength of the number.
    """
    return quality == "Good"


__all__ = ["Quality", "actionable", "believable"]
