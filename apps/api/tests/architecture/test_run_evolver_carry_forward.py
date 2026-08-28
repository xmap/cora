"""Architecture fitness: every arm of the Run evolver carries every
additive state field, including the genesis arm.

The Run aggregate accreted a wide additive-field set (parameter
overrides, the genesis decision link, campaign membership, calibration
pins, hold claims). Two distinct ways a field silently disappears on
replay:

  - A non-genesis arm constructs `Run(id=..., name=..., status=...)`
    without explicitly threading an additive field through from
    `prior`, wiping it to its default on that transition.
  - The GENESIS arm's `RunStarted(...)` match pattern never
    destructures a field the event carries, and its `Run(...)` call
    never sets it, so the field never reaches state on ANY run, ever.

`started_by_decision_id` was the second kind: `RunStarted` carried
`decided_by_decision_id` end to end through the command, decider,
route, and MCP tool, but the evolver's genesis arm never destructured
it, so it silently dropped on every run. `test_procedure_evolver_carry_forward.py`'s
own pattern (the established precedent for the first kind) explicitly
exempts the genesis arm, on the reasoning that genesis "writes /
defaults every field at initial-state construction", which is true for a field
that IS in the constructor call, useless for one that never was. This
fitness test checks both kinds: genesis must set every additive field
by name, and every non-genesis arm must carry each field as
`prior.<field>` unless declared a writer.

Precedent: `test_procedure_evolver_carry_forward.py`, same structural
AST shape for the non-genesis half. Behavior-side per-arm preservation
coverage lives in `tests/unit/run/test_run_evolver.py`; this fitness
exists because behavior tests only catch arms and fields someone
remembered to parametrize.

## What is checked

For the genesis arm (`RunStarted`):

  - the `return Run(...)` call must pass every field in
    `_WRITER_ARMS_PER_FIELD` as a keyword (any expression; genesis is where
    fields legitimately get their real value from the event).

For every other `case <EventName>(...):` arm that builds a
`return Run(...)`:

  - provenance-only arms that return `require_state(...)` (no
    `Run(...)` constructor) are exempt: passthrough preserves every
    field by definition.
  - every other arm MUST pass `<field>=prior.<field>` for each
    additive field, UNLESS the arm is a declared per-field writer (it
    legitimately sets that field from the event or a computation).

`status` and `hold_claims`'s close cousin `conduct_mode` are handled
like any other additive field here; `status` itself is excluded, since
it is the primary lifecycle indicator that legitimately changes on
almost every arm by design, not an additive denorm.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EVOLVER_PATH = (
    _REPO_ROOT / "apps" / "api" / "src" / "cora" / "run" / "aggregates" / "run" / "evolver.py"
)

_GENESIS_ARM = "RunStarted"

# Every additive field the genesis arm must set, and the arms (besides
# genesis) that legitimately WRITE each one instead of carrying
# `prior.<field>` forward. A field absent from this dict is not checked.
_WRITER_ARMS_PER_FIELD: dict[str, frozenset[str]] = {
    "id": frozenset(),
    "name": frozenset(),
    "plan_id": frozenset(),
    "subject_id": frozenset(),
    "raid": frozenset(),
    "conduct_mode": frozenset(),
    "override_parameters": frozenset(),
    "effective_parameters": frozenset({"RunAdjusted"}),
    "trigger_source": frozenset(),
    "started_by_decision_id": frozenset(),
    "observation_logbook_id": frozenset({"RunObservationLogbookOpened"}),
    "external_refs": frozenset(),
    "campaign_id": frozenset({"RunAddedToCampaign", "RunRemovedFromCampaign"}),
    "last_adjusted_at": frozenset({"RunAdjusted"}),
    "last_adjusted_by": frozenset({"RunAdjusted"}),
    "adjustment_count": frozenset({"RunAdjusted"}),
    "pinned_calibration_ids": frozenset(),
    "input_dataset_ids": frozenset(),
    "actuation_kind": frozenset({"RunCompleted", "RunAborted"}),
    "hold_claims": frozenset(
        {"RunHeld", "RunResumed", "RunCompleted", "RunAborted", "HoldClaimReleased"}
    ),
    # Declared at genesis and never rewritten: a Run's beam need is a
    # property of the work, not of any transition it makes.
    "beam_requirement": frozenset(),
}

#: `status` is the one field every arm sets structurally: changing it is
#: what a transition arm exists to do. Registered so the drift catcher
#: can tell it apart from a field someone forgot to thread.
_STRUCTURAL_FIELDS = frozenset({"status"})


def _arm_event_type_name(case_node: ast.match_case) -> str | None:
    pattern = case_node.pattern
    if isinstance(pattern, ast.MatchClass) and isinstance(pattern.cls, ast.Name):
        return pattern.cls.id
    return None


def _return_run_kwargs(case_node: ast.match_case) -> dict[str, ast.expr] | None:
    """Kwargs from the `return Run(...)` call in this arm, or None when
    the arm constructs no Run (it returns require_state/state directly
    -- a passthrough that preserves every field)."""
    for stmt in ast.walk(case_node):
        if (
            isinstance(stmt, ast.Return)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id == "Run"
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
def test_run_evolver_genesis_arm_sets_every_additive_field() -> None:
    """The RunStarted arm's `Run(...)` call names every additive field.

    A field the event carries but genesis never passes to `Run(...)`
    never reaches state on any run, on any transition, ever -- the
    exact shape of the `started_by_decision_id` bug this test guards
    against recurring."""
    cases = _find_evolve_match_cases()
    genesis_case = next((c for c in cases if _arm_event_type_name(c) == _GENESIS_ARM), None)
    assert genesis_case is not None, f"Could not locate the {_GENESIS_ARM} arm"
    kwargs = _return_run_kwargs(genesis_case)
    assert kwargs is not None, f"{_GENESIS_ARM} arm does not construct Run(...)"
    missing = [field for field in _WRITER_ARMS_PER_FIELD if field not in kwargs]
    assert not missing, (
        f"The {_GENESIS_ARM} (genesis) arm's Run(...) call omits: {', '.join(missing)}.\n"
        "A field genesis never sets never reaches Run state on any run, on any\n"
        "transition, regardless of what every other arm does. Add it to the\n"
        "genesis Run(...) call, or remove it from _WRITER_ARMS_PER_FIELD if it\n"
        "is genuinely not an additive state field."
    )


@pytest.mark.architecture
def test_carry_forward_field_registry_covers_every_run_field() -> None:
    """`_WRITER_ARMS_PER_FIELD` must enumerate every non-structural field
    on the Run dataclass.

    Without this the two guards below silently narrow: they range only
    over the fields someone remembered to list, so a NEW additive field
    is unchecked from the moment it lands and every arm that drops it
    passes clean, while the suite still reads as a full-matrix
    guarantee. That is the same blindness that let the
    `started_by_decision_id` genesis bug land.
    """
    import dataclasses

    from cora.run.aggregates.run.state import Run

    actual = {f.name for f in dataclasses.fields(Run)}
    registered = set(_WRITER_ARMS_PER_FIELD) | _STRUCTURAL_FIELDS
    unregistered = actual - registered
    stale = registered - actual
    assert not unregistered, (
        "Run gained field(s) the carry-forward guards do not range over, "
        "so they are blind to them:\n"
        + "\n".join(f"  - {f}" for f in sorted(unregistered))
        + "\n\nAdd each to `_WRITER_ARMS_PER_FIELD` (empty frozenset when no arm "
        "writes it), or to `_STRUCTURAL_FIELDS` when every arm sets it directly."
    )
    assert not stale, "The carry-forward guards name field(s) Run no longer has:\n" + "\n".join(
        f"  - {f}" for f in sorted(stale)
    )


@pytest.mark.architecture
def test_run_evolver_non_genesis_arms_carry_all_additive_fields() -> None:
    """Every non-genesis Run-constructing arm threads each additive
    field as `<field>=prior.<field>` unless it is a declared writer of
    that field."""
    violations: list[str] = []
    for case in _find_evolve_match_cases():
        event_name = _arm_event_type_name(case)
        if event_name is None:
            continue  # wildcard `case _:` (assert_never guard)
        if event_name == _GENESIS_ARM:
            continue  # checked separately: genesis writes every field
        kwargs = _return_run_kwargs(case)
        if kwargs is None:
            continue  # passthrough arm (returns require_state/state); preserves all
        for field, writer_arms in _WRITER_ARMS_PER_FIELD.items():
            if event_name in writer_arms:
                continue
            value = kwargs.get(field)
            if value is None:
                violations.append(
                    f"  - {event_name}: missing `{field}=prior.{field}` kwarg in Run(...)"
                )
                continue
            if not _is_prior_attribute_access(value, field):
                violations.append(
                    f"  - {event_name}: `{field}=...` is not "
                    f"`prior.{field}` (got `{ast.unparse(value)}`)"
                )
    assert not violations, (
        "Run evolver arms drop an additive-state field on replay.\n"
        "Every non-genesis arm that constructs `Run(...)` must thread each\n"
        "additive field as `<field>=prior.<field>` unless it legitimately\n"
        "writes that field (see `_WRITER_ARMS_PER_FIELD`). Otherwise the field\n"
        "silently wipes to its default on next replay. Add the carry-forward\n"
        "kwarg, or register a new writer arm with rationale.\n\n"
        "Violations:\n" + "\n".join(violations)
    )
