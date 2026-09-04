"""Architecture fitness: every `ConductorResult(...)` construction site that
leaves a field at its default must be an explicitly REGISTERED, understood
omission, not a hand-copy that silently dropped something.

Three field-drops shipped from exactly this shape: a fresh `ConductorResult(
a=x.a, b=x.b, ...)` built next to an existing result/merged instance already
in scope, hand-listing only SOME of its fields. #744 fixed four sites in
`conduct` / `conduct_or_hold` / `conduct_from`; a follow-up commit found and
fixed five more in `conduct_until_converged` / `conduct_until_advised` that
the same review had missed. See [[project_field_drop_bug_class]].

A `dataclasses.replace(source, **overrides)` call is complete by construction
(everything not overridden survives), so it needs no entry here and this test
never looks at `replace(` calls at all. The sites this guards are the direct
`ConductorResult(...)` constructions -- every one of the fourteen that remain
after the fixes above either builds a genuinely fresh result (nothing has run
yet, so an empty ledger is correct) or threads every field it can, and this
test PINS which fields each site is known to leave at their default and why.

## Why a registry, not a blanket "must set every field" rule

Several sites are legitimately fresh: a pre-`start_procedure` lifecycle
rejection has run no steps, so `measurements=()` / `substrate_writes={}` are
truthful, not dropped. A blanket rule would force those sites to spell out
empty values for no benefit. The registry instead names, per site, EXACTLY
which fields it leaves defaulted -- so a change to what a site omits (drops
MORE than before, or unexpectedly fewer) is caught, and a genuinely new
omission needs a deliberate entry, not a silent pass.

## The forcing function this exists for

Adding a field to `ConductorResult` (the closing-steps design's
`closing_failures` is the next one) makes every currently-registered site
"wrong" the moment that field isn't threaded: the site's ACTUAL omitted set
now includes the new field, which no longer matches its REGISTERED omitted
set, so this test fails at every site, not just new ones. The author is then
forced to decide, per site, whether the new field belongs in that site's
omission (nothing to report) or must be threaded from a prior result.
"""

from __future__ import annotations

import ast
import dataclasses
from collections import defaultdict
from pathlib import Path

import pytest

from cora.operation.conductor import ConductorResult

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONDUCTOR_PATH = _REPO_ROOT / "apps" / "api" / "src" / "cora" / "operation" / "conductor.py"

#: Fields with no default: always present in every construction (Python itself
#: raises TypeError otherwise), so they need no tracking here.
_REQUIRED_FIELDS = frozenset({"procedure_id", "completed_count"})

#: Pre-`start_procedure` lifecycle rejections: no step has run, so the entire
#: ledger is correctly empty. `closing_failures` too: closing has not run.
_PRE_START_OMISSIONS = frozenset(
    {
        "actuation_kind",
        "artifacts",
        "closing_failures",
        "held",
        "measurements",
        "outputs",
        "substrate_writes",
    }
)

#: Registry of every direct `ConductorResult(...)` site, keyed by
#: (enclosing function name, 1-indexed occurrence within that function in
#: source order), mapped to the EXACT set of fields it leaves at their
#: default. See the module docstring for what this protects.
#:
#: `closing_failures` was added to EVERY entry below in one pass when the
#: field landed: none of these 14 sites runs `_run_closing` (that only
#: happens in the wrapper methods' terminal RETURN via `replace()`, which
#: this test never inspects), so every site correctly omits it. This is the
#: exact forcing function the module docstring describes -- the guard failed
#: at every registered site the moment the field existed, and the fix at
#: each site was "yes, still correctly omitted," not a code change.
_EXPECTED_OMISSIONS: dict[tuple[str, int], frozenset[str]] = {
    # execute(): per-step and final results are built straight from local
    # data (the actuation observer, the compute accumulator, a running
    # count), never copied from a stale prior ConductorResult. `held` is
    # correctly absent: execute() itself never holds anything. Closing only
    # ever runs from a wrapper's terminal branch, never inside execute().
    ("execute", 1): frozenset({"closing_failures", "held"}),
    ("execute", 2): frozenset({"closing_failures", "failure", "held"}),
    # execute_from(): an ActionStep/ComputeStep halt-for-operator or a step
    # failure returns before any ComputeStep could run, so measurements /
    # artifacts / outputs are correctly empty; a resume replay never holds.
    ("execute_from", 1): frozenset(
        {"artifacts", "closing_failures", "held", "measurements", "outputs"}
    ),
    ("execute_from", 2): frozenset(
        {"artifacts", "closing_failures", "held", "measurements", "outputs"}
    ),
    ("execute_from", 3): frozenset(
        {"artifacts", "closing_failures", "held", "measurements", "outputs"}
    ),
    ("execute_from", 4): frozenset(
        {"artifacts", "closing_failures", "failure", "held", "measurements"}
    ),
    # Pre-start lifecycle failures: start_procedure itself was rejected, so
    # no step ever ran.
    ("conduct", 1): _PRE_START_OMISSIONS,
    ("conduct_or_hold", 1): _PRE_START_OMISSIONS,
    ("conduct_until_converged", 1): _PRE_START_OMISSIONS,
    ("conduct_until_advised", 1): _PRE_START_OMISSIONS,
    # _abort_unconverged_cap / _abort_absolute_ceiling thread the last pass's
    # ledger through a None-safe ternary (2026-08-29 fix); `held` is the only
    # remaining gap, correctly: neither loop-top abort ever holds. Closing
    # steps are v1-refused for the loop slices, so closing_failures is
    # correctly always empty here too.
    ("_abort_unconverged_cap", 1): frozenset({"closing_failures", "held"}),
    ("_abort_absolute_ceiling", 1): frozenset({"closing_failures", "held"}),
    # _hold_driver_stood_down: the same loop-top position as the two aborts
    # above, and it threads the last pass's ledger the same None-safe way, so
    # closing_failures is the only gap. Correct for the same reason: closing
    # steps are v1-refused for the loop slices, and a hold is a pause rather
    # than a terminal, so no closing has run to report. `held` is NOT omitted
    # here, unlike the aborts: parking the Procedure is the whole point, and
    # the field carries whether the park actually took.
    ("_hold_driver_stood_down", 1): frozenset({"closing_failures"}),
    # conduct_until_advised_from(): a frontier brain fault before any pass ran
    # (no execute() call yet, so no ledger to carry), and a resume-straight-
    # to-Stop synthetic placeholder fed into _complete_advised (same reason).
    ("conduct_until_advised_from", 1): frozenset(
        {"artifacts", "closing_failures", "held", "measurements", "outputs", "substrate_writes"}
    ),
    ("conduct_until_advised_from", 2): frozenset(
        {
            "actuation_kind",
            "artifacts",
            "closing_failures",
            "failure",
            "held",
            "measurements",
            "outputs",
            "substrate_writes",
        }
    ),
}


def _construction_sites() -> list[tuple[str, int, frozenset[str]]]:
    """Every direct `ConductorResult(...)` call as (function, ordinal, omitted).

    `ordinal` is the 1-indexed occurrence of the call within its enclosing
    function, in source order -- stable as long as sites are not reordered
    within the same function. `dataclasses.replace(...)` calls are a
    different `ast.Call.func` name and never appear here."""
    tree = ast.parse(_CONDUCTOR_PATH.read_text(encoding="utf-8"))
    all_fields = {f.name for f in dataclasses.fields(ConductorResult)}
    counters: dict[str, int] = defaultdict(int)
    sites: list[tuple[str, int, frozenset[str]]] = []

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name) and node.func.id == "ConductorResult":
                fn = self.stack[-1] if self.stack else "<module>"
                counters[fn] += 1
                passed = {kw.arg for kw in node.keywords if kw.arg is not None}
                omitted = frozenset(all_fields - passed - _REQUIRED_FIELDS)
                sites.append((fn, counters[fn], omitted))
            self.generic_visit(node)

    _Visitor().visit(tree)
    return sites


@pytest.mark.architecture
def test_every_conductor_result_omission_is_registered() -> None:
    """A direct `ConductorResult(...)` call may omit fields only as registered."""
    violations: list[str] = []
    seen: set[tuple[str, int]] = set()
    for fn, ordinal, omitted in _construction_sites():
        key = (fn, ordinal)
        seen.add(key)
        if not omitted:
            continue
        expected = _EXPECTED_OMISSIONS.get(key)
        if expected is None:
            violations.append(
                f"  - {fn}#{ordinal}: silently omits {sorted(omitted)} with no "
                "registry entry -- thread the field(s) from an existing result "
                "or register the omission in `_EXPECTED_OMISSIONS` with a reason"
            )
        elif expected != omitted:
            violations.append(
                f"  - {fn}#{ordinal}: omits {sorted(omitted)}, registry expects "
                f"{sorted(expected)} -- a field's coverage changed; update "
                "`_EXPECTED_OMISSIONS` deliberately"
            )
    assert not violations, (
        "ConductorResult construction site(s) silently drop a field. See "
        "[[project_field_drop_bug_class]].\n" + "\n".join(violations)
    )
    stale = set(_EXPECTED_OMISSIONS) - seen
    assert not stale, (
        "`_EXPECTED_OMISSIONS` names site(s) that no longer exist (renamed "
        "function, removed branch, or a shifted ordinal from reordering calls "
        "within one function):\n"
        + "\n".join(f"  - {fn}#{ordinal}" for fn, ordinal in sorted(stale))
    )
