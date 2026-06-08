"""Pin: every single-field display-name VO uses `@bounded_name`.

The trimmed-bounded-name VO pattern (frozen dataclass with a single
`value: str` field whose class name ends in `Name`) has 28 sites
across the codebase. They share byte-identical trim + length-check
logic via `cora.shared.bounded_text.bounded_name`. A NEW
*Name VO that hand-rolls its own `__post_init__` would be the 29th
reinvention; this test fails at PR time so reviewers catch it before
merge and either route the new VO through the decorator or argue
explicitly why this one needs a bespoke shape.

The check is structural:

  - frozen dataclass (matches `test_domain_dataclasses_are_frozen`)
  - exactly one field, declared as `value: str`
  - class name matches `*Name` (covers `ActorName`, `RoleName`,
    `SlotName`, `ToolName`, `ChannelName`, `AssetOwnerName`, etc.;
    the trailing `Name` is the family-noun primacy marker from
    R3 in `project_naming_conventions.md`)

Hits: every such class MUST carry `@bounded_name(...)` somewhere in
its decorator list.

VOs that legitimately deviate (composite multi-field shapes like
`AssetPort`, `Drawing`, `AssetOwner`, `AlternateIdentifier`;
non-name single-field VOs like `CautionText`; VOs with non-standard
rejection semantics like `CalibrationDescription`) all fail at least
one of the three structural predicates above and are correctly
excluded; no allowlist needed.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _is_value_str_field(node: ast.stmt) -> bool:
    """True for an annotated assignment of the form `value: str` (no default)."""
    if not isinstance(node, ast.AnnAssign):
        return False
    if not (isinstance(node.target, ast.Name) and node.target.id == "value"):
        return False
    if node.value is not None:
        return False
    return isinstance(node.annotation, ast.Name) and node.annotation.id == "str"


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


def _decorator_name(decorator: ast.expr) -> str | None:
    """Return the bare callable name of a decorator, whether bare or called."""
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    if isinstance(decorator, ast.Name):
        return decorator.id
    if isinstance(decorator, ast.Attribute):
        return decorator.attr
    return None


def _has_bounded_name_decorator(class_def: ast.ClassDef) -> bool:
    return any(_decorator_name(d) == "bounded_name" for d in class_def.decorator_list)


def _has_frozen_dataclass_decorator(class_def: ast.ClassDef) -> bool:
    return any(_is_frozen_dataclass_decorator(d) for d in class_def.decorator_list)


def _is_single_value_str_class(class_def: ast.ClassDef) -> bool:
    """True if the only field declared in the body is `value: str`."""
    field_assigns = [
        node for node in class_def.body if isinstance(node, (ast.AnnAssign, ast.Assign))
    ]
    if len(field_assigns) != 1:
        return False
    return _is_value_str_field(field_assigns[0])


def _state_files() -> list[Path]:
    """Tracked `state.py` files under `cora/*/aggregates/*/`."""
    return sorted(
        path
        for path in tracked_python_files()
        if path.name == "state.py" and "/aggregates/" in str(path)
    )


def _candidate_classes(tree: ast.AST) -> list[ast.ClassDef]:
    """Frozen-dataclass classes named `*Name` with a single `value: str` field."""
    candidates: list[ast.ClassDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not node.name.endswith("Name"):
            continue
        if not _has_frozen_dataclass_decorator(node):
            continue
        if not _is_single_value_str_class(node):
            continue
        candidates.append(node)
    return candidates


@pytest.mark.architecture
@pytest.mark.parametrize("path", _state_files(), ids=_qualified)
def test_bounded_name_decorator_wraps_display_name_vos(path: Path) -> None:
    """Every `*Name` frozen dataclass with a single `value: str` field uses `@bounded_name`."""
    tree = ast.parse(path.read_text())
    offenders = [
        f"line {cls.lineno}: {cls.name}"
        for cls in _candidate_classes(tree)
        if not _has_bounded_name_decorator(cls)
    ]
    assert not offenders, (
        f"{_qualified(path)} declares display-name VO(s) without `@bounded_name`:\n  "
        + "\n  ".join(offenders)
        + "\n\nA frozen dataclass named `*Name` with a single `value: str` field is the "
        "29th reinvention of the trimmed-bounded-name VO pattern. Decorate the class with "
        "`@bounded_name(max_length=..., error_class=...)` from "
        "`cora.shared.bounded_text` instead of hand-rolling a `__post_init__`. "
        "If the VO needs non-standard rejection semantics (empty-after-trim allowed, "
        "regex validation, multi-field composite), give it a shape that fails one of "
        "the three structural predicates this fitness function checks (drop the "
        "single-field `value: str` shape or rename away from `*Name`) and document why."
    )
