"""Pin: self-referential parent pointers on aggregate state are named
exactly `parent_id`, never the verbose `parent_<aggregate>_id` or
`part_of_<aggregate>_id` form.

The aggregate's own module namespace already disambiguates the target
type: an `Asset.parent_id` field can only point at another `Asset`,
because it sits inside `cora.equipment.aggregates.asset.state.Asset`.
Adding the aggregate's own name to the field name is verbose
redundancy that drifts across BCs once enough sites accumulate.

This pin catches the verbose form structurally:

  - For every aggregate `state.py` at `cora/<bc>/aggregates/<name>/state.py`,
    walk every annotated field in every frozen dataclass in that module.
  - Reject any field whose name matches
    `^parent_<name>_id$` or `^part_of_<name>_id$` (case-insensitive on the
    aggregate-name portion). Such a field is a verbose self-reference
    that should have been named `parent_id`.

Cross-aggregate parent pointers (for example `Procedure.parent_run_id`
references a Run, not a Procedure; `Visit.parent_surface_id` references
a Surface, not a Visit) legitimately need the cross-aggregate qualifier
and are NOT flagged because the qualifier is NOT the aggregate's own
name.

The 7 self-parent sites that currently follow the convention
(`Asset.parent_id`, `Mount.parent_id`, `Frame.parent_id`,
`Caution.parent_id`, `Clearance.parent_id`, `Visit.parent_id`,
`Facility.parent_id`; the companion `Decision.parent_id` also follows
it) all pass; a future
slice that introduces a `parent_asset_id` style verbose self-reference
on Asset state fails this test loudly at PR time.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


_AGGREGATE_PATH_PATTERN = re.compile(r"/aggregates/(?P<aggregate>[a-z_][a-z0-9_]*)/state\.py$")


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _aggregate_name_for(path: Path) -> str | None:
    """Return the aggregate directory name for an `aggregates/<name>/state.py`
    path, or None for state files outside that layout."""
    match = _AGGREGATE_PATH_PATTERN.search(str(path))
    return match.group("aggregate") if match else None


def _is_frozen_dataclass_decorator(decorator: ast.expr) -> bool:
    """True for `@dataclass(frozen=True)` (call form with the literal True)."""
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    name = (
        func.id
        if isinstance(func, ast.Name)
        else func.attr
        if isinstance(func, ast.Attribute)
        else None
    )
    if name != "dataclass":
        return False
    frozen_kw = next((kw for kw in decorator.keywords if kw.arg == "frozen"), None)
    if frozen_kw is None:
        return False
    return isinstance(frozen_kw.value, ast.Constant) and frozen_kw.value.value is True


def _has_frozen_dataclass_decorator(class_def: ast.ClassDef) -> bool:
    return any(_is_frozen_dataclass_decorator(d) for d in class_def.decorator_list)


def _annotated_field_names(class_def: ast.ClassDef) -> list[tuple[int, str]]:
    """Return (lineno, name) for every annotated assignment in the class body."""
    names: list[tuple[int, str]] = []
    for node in class_def.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append((node.lineno, node.target.id))
    return names


def _aggregate_state_files() -> list[Path]:
    """Tracked `state.py` files under `cora/<bc>/aggregates/<name>/`."""
    return sorted(path for path in tracked_python_files() if _aggregate_name_for(path) is not None)


def _verbose_self_parent_pattern(aggregate: str) -> re.Pattern[str]:
    """`parent_<aggregate>_id` or `part_of_<aggregate>_id`, case-insensitive
    on the aggregate-name portion (the aggregate dir is already lowercase
    by convention, but this stays robust)."""
    return re.compile(
        rf"^(?:parent|part_of)_{re.escape(aggregate)}_id$",
        flags=re.IGNORECASE,
    )


@pytest.mark.architecture
@pytest.mark.parametrize("path", _aggregate_state_files(), ids=_qualified)
def test_self_parent_field_named_parent_id(path: Path) -> None:
    """Every self-referential parent field on an aggregate's state MUST be
    named exactly `parent_id`, never the verbose `parent_<aggregate>_id`
    or `part_of_<aggregate>_id` form."""
    aggregate = _aggregate_name_for(path)
    assert aggregate is not None  # guaranteed by _aggregate_state_files filter
    pattern = _verbose_self_parent_pattern(aggregate)

    tree = ast.parse(path.read_text())
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _has_frozen_dataclass_decorator(node):
            continue
        for lineno, field_name in _annotated_field_names(node):
            if pattern.match(field_name):
                offenders.append(
                    f"line {lineno}: {node.name}.{field_name} is a verbose "
                    f"self-reference; rename to `parent_id`"
                )

    assert not offenders, (
        f"{_qualified(path)} has verbose self-parent field(s):\n  "
        + "\n  ".join(offenders)
        + "\n\nSelf-referential parent pointers on aggregate state use the field "
        "name `parent_id`, NOT `parent_<aggregate>_id` or "
        "`part_of_<aggregate>_id`. The aggregate's own module namespace already "
        "disambiguates the target type. See "
        "[CONTRIBUTING.md / docs/reference/conventions.md] for the rule and "
        "the sites already following it (Asset, Mount, Frame, Caution, "
        "Clearance, Visit, Facility, Decision)."
    )
