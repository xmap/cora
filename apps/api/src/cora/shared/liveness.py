"""Commands a principal an operator switched off may still issue.

Sibling of `cora.shared.consequence`: a BC-agnostic set of command names
that a gate consults, living in `shared` because the names it holds
belong to Operation, Run, and Trust while the gate that reads it lives
in Trust.

## The question this set answers, which is not the one it was first copied from

An earlier version of this set was lifted verbatim from the
human-envelope design's closing-and-recording and brake lists. Those
lists were written for a WINDOW conjunct, where a twelve-hour scan
crosses a beamtime boundary and the principal is entirely legitimate;
the clock moved, not the person. Liveness is a different question: an
operator deliberately reached for a switch and turned this principal
off.

The two answers diverge, and `resume_procedure` is where. Letting a
scientist resume across a window boundary is obviously right. Letting
someone an operator just switched off resume a held Procedure is
obviously wrong, because a resumed Procedure walks real setpoints, so
the exemption would have handed a revoked principal the power to
restart beam motion. That is the inverse of a brake. It was in the
inherited list and it is not here.

So the set is derived from one question, asked directly:

> What may a principal an operator deliberately switched off still do?

Two answers, and nothing else:

  1. STOP work that is already running. Refusing a brake means an
     operator who switches someone off has, in the same act, taken away
     that person's ability to halt what they started. The eligible set
     for moving the system toward safety must be strictly WIDER than for
     routine work, never narrower.

  2. RECORD what already happened. The photons already hit the detector.
     Refusing the append does not un-run the scan, it only makes CORA's
     record wrong, and a wrong record is the one failure a system of
     record cannot absorb. Refusing `complete_procedure` additionally
     strands the Procedure in Running with its own abort denied by the
     same conjunct.

Deliberately NOT here, having been considered:

  - Anything that STARTS or RESTARTS work, `resume_procedure` included.
  - `AbortVisit`, `HoldCampaign`: terminal or organizational, not the
    halting of physical work in progress. Their siblings `CancelVisit`
    and `CompleteVisit` are not exempt either, and an exemption that
    covers one of a family and not the rest reads as an oversight.

## Scope limit: no target scoping, and that is deliberate

Membership is by COMMAND NAME. A switched-off principal still in a
Policy's permitted set may brake or append against ANY Run or Procedure,
not only their own. A security review flagged this; the decision is to
accept it here and fix the real cause elsewhere, for four reasons.

**The gap is Policy's, not this set's.** `Policy` carries
`permitted_principal_ids` and `permitted_commands`, both flat, and no
target dimension whatsoever. An ACTIVE principal permitted `AbortRun` can
already abort any run at the facility. This set inherits that absence; it
does not create it, and it grants a switched-off principal nothing they
did not have a moment earlier.

**Scoping only the switched-off would invent a narrowing that exists for
nobody.** What instrument does a facility issue that binds a scientist's
brake to their own scans? None. Authoring one here would make a withdrawn
principal MORE constrained than a permitted one on the identical command,
which is a new asymmetry in the opposite direction rather than a fix for
the old one.

**The design rule points the other way for brakes.** For commands that
move the system toward a safer state the eligible set must be strictly
WIDER than for routine work, never narrower. Someone hitting the brake on
a runaway scan is the system working, whatever an operator has since done
to their account.

**The sharpest edge is already blunted.** `StopRun` is the sole member of
`COMMANDS_REQUIRING_RATIFICATION`, so the most consequential brake needs a
second principal regardless. And since `ActorDeactivated` began cascading
into `authority_revocation_holder`, a switched-off principal's OWN runs
are held the moment they are withdrawn, so the residual reach is over
other people's work only.

What stays uncomfortable, honestly: a principal an operator withdrew is
likelier to be acting badly than one who was not, so preserving their
reach is worse than preserving anyone else's, even though the reach is
identical. That argues for giving Policy a target dimension, which would
bind every principal at once. It does not argue for a partial fix wired
through the liveness door.

HAND-MAINTAINED, DELIBERATELY TEMPORARY. When the OperationClass map
lands this becomes derived (every Halt-class and Record-class command)
and stops being something a new slice can forget to join.
"""

from typing import Final

# Stops work already in progress. See the module docstring for why the
# eligible set here must be wider than for routine commands.
_BRAKE: Final[frozenset[str]] = frozenset(
    {
        "StopRun",
        "HoldRun",
        "AbortRun",
        "TruncateRun",
        "HoldProcedure",
        "AbortProcedure",
        "TruncateProcedure",
        "HoldVisit",
    }
)

# States what already happened. Refusing these corrupts the record
# rather than preventing anything.
_RECORDING: Final[frozenset[str]] = frozenset(
    {
        "CompleteRun",
        "CompleteProcedure",
        "EndProcedureIteration",
        "AppendProcedureActivities",
        "AppendProcedureOutcomes",
        "AppendProcedureDiagnostics",
        "AppendObservations",
    }
)

LIVENESS_EXEMPT_COMMANDS: Final[frozenset[str]] = _BRAKE | _RECORDING


def is_liveness_exempt(command_name: str) -> bool:
    """True if liveness may never refuse `command_name`."""
    return command_name in LIVENESS_EXEMPT_COMMANDS


__all__ = ["LIVENESS_EXEMPT_COMMANDS", "is_liveness_exempt"]
