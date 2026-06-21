"""Architecture fitness: every non-genesis, Procedure-constructing arm of
the Procedure evolver MUST carry all additive state fields through from
prior state.

The Procedure aggregate accreted a wide additive-field set (the
iteration denorms, the recipe/capability binding, the activity logbook
id, the actuation-kind provenance carrier). Constructing
`Procedure(id=..., name=..., status=...)` on a new transition arm
without explicitly threading those fields silently WIPES them to their
defaults (empty frozenset / None / 0) on the next replay. The Tier-1
`ProcedureHeld` / `ProcedureResumed` arms are the latest pair that must
carry the iteration denorms verbatim; this AST check pins the whole
matrix so the bug class cannot recur when a new arm lands.

Precedent: `test_asset_evolver_lifecycle_dates_carry_forward.py` (same
structural AST shape, narrower field set). Behavior-side per-arm
preservation coverage lives in `tests/unit/operation/test_procedure_evolver.py`;
this fitness exists because behavior tests only catch arms someone
remembered to parametrize.

## What is checked

For every `case <EventName>(...):` arm in `evolve` that builds a
`return Procedure(...)`:

  - the genesis arm (`ProcedureRegistered`) is exempt: it writes /
    defaults every field at initial-state construction.
  - provenance-only arms that return `require_state(...)` (no
    `Procedure(...)` constructor) are exempt: passthrough preserves
    every field by definition.
  - every other arm MUST pass `<field>=prior.<field>` for each
    carry-forward field, UNLESS the arm is a declared per-field writer
    (it legitimately sets that field from the event or a computation).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EVOLVER_PATH = (
    _REPO_ROOT
    / "apps"
    / "api"
    / "src"
    / "cora"
    / "operation"
    / "aggregates"
    / "procedure"
    / "evolver.py"
)

_GENESIS_ARM = "ProcedureRegistered"

# Carry-forward fields and the arms that legitimately WRITE each (so are
# exempt from the `=prior.<field>` requirement for that field). The
# genesis arm writes every field and is exempt globally below.
_WRITER_ARMS_PER_FIELD: dict[str, frozenset[str]] = {
    "kind": frozenset(),
    "target_asset_ids": frozenset(),
    "parent_run_id": frozenset(),
    "activity_logbook_id": frozenset({"ProcedureActivitiesLogbookOpened"}),
    "capability_id": frozenset(),
    "recipe_id": frozenset(),
    "current_iteration_index": frozenset({"ProcedureIterationStarted", "ProcedureIterationEnded"}),
    "iteration_count": frozenset({"ProcedureIterationStarted"}),
    "consecutive_unconverged_iterations": frozenset({"ProcedureIterationEnded"}),
    "max_consecutive_unconverged_iterations": frozenset(),
    # Terminal arms snapshot the Conductor's observed kind from the event;
    # ProcedureHeld MERGES the conduct's observed-so-far kind into state (via
    # merge_actuation_kinds) so the pre-hold provenance survives the
    # hold->resume boundary.
    "actuation_kind": frozenset({"ProcedureCompleted", "ProcedureAborted", "ProcedureHeld"}),
}


def _arm_event_type_name(case_node: ast.match_case) -> str | None:
    pattern = case_node.pattern
    if isinstance(pattern, ast.MatchClass) and isinstance(pattern.cls, ast.Name):
        return pattern.cls.id
    return None


def _return_procedure_kwargs(case_node: ast.match_case) -> dict[str, ast.expr] | None:
    """Kwargs from the `return Procedure(...)` call in this arm, or None
    when the arm constructs no Procedure (it returns require_state /
    state directly -- a passthrough that preserves every field)."""
    for stmt in ast.walk(case_node):
        if (
            isinstance(stmt, ast.Return)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id == "Procedure"
        ):
            return {kw.arg: kw.value for kw in stmt.value.keywords if kw.arg is not None}
    return None


def _is_prior_attribute_access(node: ast.expr, field: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == field
        and isinstance(node.value, ast.Name)
        and node.value.id == "prior"
    )


def _find_evolve_match_cases() -> list[ast.match_case]:
    tree = ast.parse(_EVOLVER_PATH.read_text(encoding="utf-8"))
    evolve_func = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "evolve"),
        None,
    )
    assert evolve_func is not None, "Could not locate `evolve` in evolver.py"
    match_stmt = next((n for n in evolve_func.body if isinstance(n, ast.Match)), None)
    assert match_stmt is not None, "Could not locate `match event:` in `evolve`"
    return list(match_stmt.cases)


@pytest.mark.architecture
def test_procedure_evolver_non_writer_arms_carry_all_additive_fields() -> None:
    """Every non-genesis Procedure-constructing arm threads each additive
    field as `<field>=prior.<field>` unless it is a declared writer of
    that field."""
    violations: list[str] = []
    for case in _find_evolve_match_cases():
        event_name = _arm_event_type_name(case)
        if event_name is None:
            continue  # wildcard `case _:` (assert_never guard)
        if event_name == _GENESIS_ARM:
            continue  # genesis writes / defaults every field
        kwargs = _return_procedure_kwargs(case)
        if kwargs is None:
            continue  # passthrough arm (returns require_state/state); preserves all
        for field, writer_arms in _WRITER_ARMS_PER_FIELD.items():
            if event_name in writer_arms:
                continue
            value = kwargs.get(field)
            if value is None:
                violations.append(
                    f"  - {event_name}: missing `{field}=prior.{field}` kwarg in Procedure(...)"
                )
                continue
            if not _is_prior_attribute_access(value, field):
                violations.append(
                    f"  - {event_name}: `{field}=...` is not "
                    f"`prior.{field}` (got `{ast.unparse(value)}`)"
                )
    assert not violations, (
        "Procedure evolver arms drop an additive-state field on replay.\n"
        "Every non-genesis arm that constructs `Procedure(...)` must thread\n"
        "each additive field as `<field>=prior.<field>` unless it legitimately\n"
        "writes that field (see `_WRITER_ARMS_PER_FIELD`). Otherwise the field\n"
        "silently wipes to its default on next replay (the dropped-iteration-\n"
        "denorm bug class). Add the carry-forward kwarg, or register a new\n"
        "writer arm with rationale.\n\n"
        "Violations:\n" + "\n".join(violations)
    )
