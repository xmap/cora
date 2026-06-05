"""Architecture fitness: every non-writer arm of the Asset evolver
MUST carry `commissioned_at` and `decommissioned_at` through from
prior state.

PIDINST v1.0 Property 11 lifecycle dates were added in slice E.1.
The `_view_assembler.py` PIDINST read path reads
`Asset.commissioned_at` to derive `publication_year` for DataCite; a
missed carry-forward arm silently wipes the field to its default
None on next replay, breaking serialization. Two arms initially
shipped without the carry (`AssetOwnerRemoved`, `AssetAttachedToFixture`);
this fitness pins the matrix so the bug class cannot recur when a
new event-type arm is added.

The check is structural (AST-based): for every `case <EventName>(...):`
arm in `evolve`, the `return Asset(...)` call inside it must contain
`commissioned_at=prior.commissioned_at` (unless the arm is exempt as
the genesis writer) AND `decommissioned_at=prior.decommissioned_at`
(unless exempt as either genesis or the terminal writer).

Behavior-side coverage lives in
`tests/unit/equipment/test_asset_lifecycle_dates_evolver.py` (per-arm
preservation tests parametrized over the full transition matrix). The
AST fitness exists because behavior tests only catch arms someone
remembered to add to the parametrize list; the structural check
catches a newly-added arm even if no behavior test was written for it.
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
    / "equipment"
    / "aggregates"
    / "asset"
    / "evolver.py"
)

# Per-field writer-arm exemptions. An arm is exempt from the carry-forward
# check for a given field when the arm WRITES that field (sets it to
# something other than `prior.<field>`), or when there is no prior state
# (the genesis arm).
#
#   commissioned_at: only `AssetRegistered` writes it (from `occurred_at`)
#   decommissioned_at: `AssetRegistered` defaults None at genesis;
#                      `AssetDecommissioned` writes from `occurred_at`
_WRITER_ARMS_PER_FIELD: dict[str, frozenset[str]] = {
    "commissioned_at": frozenset({"AssetRegistered"}),
    "decommissioned_at": frozenset({"AssetRegistered", "AssetDecommissioned"}),
}


def _arm_event_type_name(case_node: ast.match_case) -> str | None:
    """Return the event class name matched by this case, or None for the
    wildcard `case _:` arm."""
    pattern = case_node.pattern
    if isinstance(pattern, ast.MatchClass) and isinstance(pattern.cls, ast.Name):
        return pattern.cls.id
    return None


def _return_asset_kwargs(case_node: ast.match_case) -> dict[str, ast.expr]:
    """Extract kwargs from the `return Asset(...)` call inside this arm.

    Returns an empty dict if the arm has no such call (which would itself
    be a violation worth surfacing, but the per-field assertion below
    will catch it as a missing kwarg).
    """
    for stmt in ast.walk(case_node):
        if (
            isinstance(stmt, ast.Return)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id == "Asset"
        ):
            return {kw.arg: kw.value for kw in stmt.value.keywords if kw.arg is not None}
    return {}


def _is_prior_attribute_access(node: ast.expr, field: str) -> bool:
    """Match the literal `prior.<field>` expression shape."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == field
        and isinstance(node.value, ast.Name)
        and node.value.id == "prior"
    )


def _find_evolve_match_cases() -> list[ast.match_case]:
    """Parse evolver.py and locate the `match event:` arms inside `evolve`."""
    tree = ast.parse(_EVOLVER_PATH.read_text(encoding="utf-8"))
    evolve_func = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "evolve"),
        None,
    )
    assert evolve_func is not None, "Could not locate `evolve` function in evolver.py"
    match_stmt = next(
        (node for node in evolve_func.body if isinstance(node, ast.Match)),
        None,
    )
    assert match_stmt is not None, "Could not locate `match event:` in `evolve`"
    return list(match_stmt.cases)


@pytest.mark.architecture
def test_asset_evolver_non_writer_arms_preserve_lifecycle_dates() -> None:
    """For every non-writer arm of `evolve`, the constructed `Asset(...)`
    call must include `commissioned_at=prior.commissioned_at` and
    `decommissioned_at=prior.decommissioned_at`.

    Pre-existing regression: `AssetOwnerRemoved` and
    `AssetAttachedToFixture` both dropped both fields on first ship of
    PIDINST slice E.1 (PR #34, 2026-06-04), silently corrupting state
    on replay for any Asset that subsequently lost an owner or was
    attached to a fixture.
    """
    violations: list[str] = []
    for case in _find_evolve_match_cases():
        event_name = _arm_event_type_name(case)
        if event_name is None:
            continue  # wildcard `case _:` (assert_never exhaustiveness guard)
        kwargs = _return_asset_kwargs(case)
        for field, writer_arms in _WRITER_ARMS_PER_FIELD.items():
            if event_name in writer_arms:
                continue
            value = kwargs.get(field)
            if value is None:
                violations.append(
                    f"  - {event_name}: missing `{field}=prior.{field}` kwarg in Asset(...)"
                )
                continue
            if not _is_prior_attribute_access(value, field):
                violations.append(
                    f"  - {event_name}: `{field}=...` is not "
                    f"`prior.{field}` (got `{ast.unparse(value)}`)"
                )
    assert not violations, (
        "Asset evolver arms missing PIDINST lifecycle-date carry-forward.\n"
        "Every non-writer arm must construct `Asset(...)` with both\n"
        "`commissioned_at=prior.commissioned_at` and\n"
        "`decommissioned_at=prior.decommissioned_at`. Otherwise the field\n"
        "wipes to its default None on next replay, breaking PIDINST\n"
        "serialization via `_view_assembler.py`.\n\n"
        "Violations:\n" + "\n".join(violations)
    )
