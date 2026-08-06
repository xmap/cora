"""Every liveness-exempt command name is a real command.

`LIVENESS_EXEMPT_COMMANDS` is the set the liveness conjunct may never
refuse: the brake (work that moves the system toward a safer state) and
the closing-and-recording set (work that finishes or reports what already
happened). Denying either is a named failure in the human-envelope
design, so the set is load-bearing rather than advisory.

It is also HAND-MAINTAINED, which is the risk this file exists to bound.
The design memo that motivates it named four brake commands while the
tree carries eleven brake-shaped ones, so a prose list was stale the day
it was written. A typo or a renamed command would silently shrink the
exemption and reintroduce exactly the lockout the set prevents, with
every other test still green.

This pins one direction only: every name here EXISTS. The other
direction (every brake-or-closing command appears here) is deliberately
not pinned, because there is no machine-readable definition of "brake"
or "closing" yet. When the OperationClass map lands, this whole set
becomes derived from the Halt and Record classes and this file is
replaced by a both-directions check.
"""

import ast
from typing import Final

import pytest

from cora.shared.liveness import LIVENESS_EXEMPT_COMMANDS
from tests.architecture.conftest import tracked_python_files


def _command_class_names() -> frozenset[str]:
    """Every command dataclass name declared under a `features/*/command.py`."""
    found: set[str] = set()
    for path in tracked_python_files():
        if path.name != "command.py" or path.parent.parent.name != "features":
            continue
        for node in ast.iter_child_nodes(ast.parse(path.read_text())):
            if isinstance(node, ast.ClassDef):
                found.add(node.name)
    return frozenset(found)


@pytest.mark.architecture
def test_liveness_exempt_command_without_a_slice_is_rejected() -> None:
    unknown = sorted(LIVENESS_EXEMPT_COMMANDS - _command_class_names())
    assert not unknown, (
        "`LIVENESS_EXEMPT_COMMANDS` names command(s) that do not exist:\n  "
        + "\n  ".join(unknown)
        + "\n\nA name that matches no command exempts nothing, so the brake or the "
        "closing command it was meant to protect is now refusable for a deactivated "
        "principal. Either the command was renamed (update the entry) or it was "
        "removed (delete it). Do not leave it: the set reads as protection it is "
        "not providing."
    )


@pytest.mark.architecture
def test_liveness_exempt_set_is_not_empty() -> None:
    """Guards the whole file against being trivially satisfied.

    An empty set passes the check above vacuously while removing every
    exemption, which is the most damaging edit this file could fail to
    catch.
    """
    assert LIVENESS_EXEMPT_COMMANDS, (
        "`LIVENESS_EXEMPT_COMMANDS` is empty, so liveness can refuse a stop, an "
        "abort, a completion, or an append. A deactivated principal mid-scan would "
        "strand the Procedure in Running with its own abort denied."
    )


# Verbs that begin or resume work. An exemption naming one hands a
# principal an operator deliberately switched off the power to set the
# system going again, which is the inverse of both justifications the
# set rests on.
_STARTING_VERBS: Final[frozenset[str]] = frozenset(
    {"Start", "Resume", "Reactivate", "Restore", "Activate", "Conduct", "Reopen"}
)


@pytest.mark.architecture
def test_liveness_exemption_for_work_starting_command_is_rejected() -> None:
    """The regression guard for the mistake this set has already made once.

    `ResumeProcedure` shipped in an earlier version of this set, copied
    from a design memo whose list was written for a WINDOW conjunct: a
    twelve-hour scan crossing a beamtime boundary, where the principal is
    entirely legitimate and only the clock moved. Liveness is an operator
    deliberately reaching for a switch, and a resumed Procedure walks
    real setpoints, so the inherited exemption let a revoked principal
    restart beam motion.

    A name check cannot decide semantics, and this one deliberately does
    not try. It catches the specific, repeatable error of adding a
    start-shaped verb to a set justified entirely by stopping and
    recording. If a genuinely start-shaped command ever belongs here,
    that needs an argument in the module docstring, not a quiet append.
    """
    starting = sorted(
        name
        for name in LIVENESS_EXEMPT_COMMANDS
        if any(name.startswith(verb) for verb in _STARTING_VERBS)
    )
    assert not starting, (
        "`LIVENESS_EXEMPT_COMMANDS` names command(s) that start or resume work:\n  "
        + "\n  ".join(starting)
        + "\n\nThe set exempts exactly two things: stopping work already running, and "
        "recording what already happened. A principal an operator switched off must not "
        "be able to set the system going again. This exact mistake shipped once, as "
        "ResumeProcedure, because a list written for a window conjunct was reused for a "
        "deliberate switch."
    )
