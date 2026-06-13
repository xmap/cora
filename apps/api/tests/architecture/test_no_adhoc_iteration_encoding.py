"""Forbid the retired ad-hoc per-iteration encoding in tracked source.

First-class Procedure iteration shipped as `ProcedureIterationStarted` /
`ProcedureIterationEnded` boundary events, an `iteration_count` denorm,
and the `proj_operation_procedure_iterations` read model. Before that,
the alignment scenarios encoded "which iteration am I on" ad-hoc by
stuffing an `iteration` key into a Check step's free-form `evidence`
payload (passed as a `iteration=<n>` kwarg to the local `_check`
helper). That convention drifted across kinds and is now retired: the
boundary events are the single source of iteration truth.

This fitness keeps the retirement sticky. It walks every tracked `.py`
under `src/cora` and `tests/` and fails on either shape of the old
encoding:

  - a dict-literal key `"iteration":` / `'iteration':` (the evidence
    payload key), or
  - a `iteration=<digit>` keyword argument (the `_check` helper form).

Both patterns are precise enough to leave the first-class field names
untouched: `iteration_index` and `iteration_count` never match (the
key form needs a colon directly after the quoted word; the kwarg form
needs `=` directly after `iteration`, which `iteration_index=` and
`iteration_count=` break). Prose and assertions that merely mention the
retired key (`evidence['iteration']` in a comment, `"iteration" not in
evidence`) also do not match, because neither is a quoted key followed
by a colon.
"""

import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import tracked_python_files, tracked_test_files

if TYPE_CHECKING:
    from pathlib import Path

# Either the quoted dict key `"iteration":` / `'iteration':`, or the
# `iteration=<digit>` kwarg. The backreference (\1) ties the closing
# quote to the opening one so only true dict-literal keys match. The
# kwarg arm needs `=` directly after `iteration` (no space: ruff-format
# normalizes kwargs that way), so the first-class `iteration_index=` /
# `iteration_count=` fields never match (the `_` breaks it) and prose
# like "2 per iteration = 4" is not caught. The colon-only key arm
# likewise leaves the bracket-subscript form `evidence['iteration']` in
# comments/asserts alone.
_FORBIDDEN = re.compile(r"""(["'])iteration\1\s*:|\biteration=[0-9]""")

_SELF_FILENAME = "test_no_adhoc_iteration_encoding.py"


def _violation_for_line(line: str) -> str | None:
    """Return the matched substring if the line carries the retired encoding."""
    match = _FORBIDDEN.search(line)
    return match.group(0) if match is not None else None


@pytest.mark.architecture
@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('evidence = {"iteration": 2}', '"iteration":'),
        ("payload = {'iteration': n}", "'iteration':"),
        ("        _check(channel=c, passed=True, iteration=1, sampled_at=t(3)),", "iteration=1"),
    ],
)
def test_forbidden_arm_matches_retired_encoding(line: str, expected: str) -> None:
    """Both shapes of the retired ad-hoc encoding are caught."""
    assert _violation_for_line(line) == expected


@pytest.mark.architecture
@pytest.mark.parametrize(
    "line",
    [
        # First-class field names must not trip the regex.
        "StartProcedureIteration(procedure_id=pid, iteration_index=1)",
        "assert proc_summary.iteration_count == 2",
        "current_iteration_index: int | None = None",
        # Prose / assertions mentioning the retired key are fine.
        "    # iteration is no longer encoded via an evidence['iteration'] key",
        'assert "iteration" not in convergence_check_payload["evidence"]',
        # Arithmetic prose with spaces around `=` must not be caught (the
        # kwarg arm is intentionally space-sensitive).
        "    # version = 4 + 2 per iteration = 4 + 2*4 = 12",
    ],
)
def test_allowed_lines_are_not_flagged(line: str) -> None:
    """The first-class fields and references to the retired key are allowed."""
    assert _violation_for_line(line) is None


@pytest.mark.architecture
def test_no_adhoc_iteration_encoding_in_tracked_source() -> None:
    """Every tracked .py under src/cora and tests/ is free of the retired encoding."""
    violations: list[tuple[Path, int, str, str]] = []
    for path in sorted(tracked_python_files() | tracked_test_files()):
        if path.name == _SELF_FILENAME:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            match = _violation_for_line(line)
            if match is not None:
                violations.append((path, lineno, match, line.rstrip()))

    if not violations:
        return

    msg_lines = [
        f"Found {len(violations)} use(s) of the retired ad-hoc iteration encoding.",
        "Iteration is first-class: use ProcedureIterationStarted/Ended + the",
        "iteration_count denorm + proj_operation_procedure_iterations instead.",
        "",
    ]
    for path, lineno, match, line in violations[:20]:
        msg_lines.append(f"  {path}:{lineno}: matched {match!r}")
        msg_lines.append(f"    {line}")
    if len(violations) > 20:
        msg_lines.append(f"  ... and {len(violations) - 20} more")
    pytest.fail("\n".join(msg_lines))
