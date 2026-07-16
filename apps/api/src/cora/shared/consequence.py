"""Consequence gate (Gate IV): the declared class of commands that require a
second, independent principal's co-signature (a Granted Ratification) before they
are admitted.

Kept in `cora.shared` (neutral) so the Run-side decider can consult it without a
Trust import, mirroring how bounded-text limits live in `cora.shared.text_bounds`.
The membership test is the gate's TRIGGER; the `ConsequenceLookup` port answers
the orthogonal COVERAGE question ("is there a Granted Ratification for this
action?"). Keeping the two separate is what keeps the gate's marginal cost a pure
fold + decider arm.

## Allowlist-first (rule-of-three deferred)

The declared class is a static frozenset of command names, mirroring the
obligation gate's allowlist and the required-role sets. A Capability-declared
`consequence_class` (per-action, data-driven) is the richer version; it is
deferred until a second in-scope command appears (rule of three). A log-folded
first-of-kind refinement of the trigger (co-sign only the FIRST time a command is
run against a scope) is a documented follow-up and does not change this module's
contract.

## v1 membership

`StopRun` only: a deliberate, non-emergency, irreversible early termination of a
running experiment. NOT `AbortRun` (emergency exit; holding an emergency for a
co-signature inverts the safety posture).
"""

from typing import Final

COMMANDS_REQUIRING_RATIFICATION: Final[frozenset[str]] = frozenset({"StopRun"})


def requires_ratification(command_name: str) -> bool:
    """Return True iff `command_name` is in the declared consequence class."""
    return command_name in COMMANDS_REQUIRING_RATIFICATION


__all__ = ["COMMANDS_REQUIRING_RATIFICATION", "requires_ratification"]
