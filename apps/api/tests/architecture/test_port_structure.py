"""Port Protocols are structurally well-formed: frozen DTOs + consistent runtime_checkable.

Companion to `test_port_naming_conventions.py` (which guards port names); these
guard port structure. Helpers are re-implemented locally rather than imported from
the sibling test (keeps each port fitness module self-contained and legible).

## Frozen DTOs

Every dataclass in a port file is `@dataclass(frozen=True)`. Port DTOs (lookup
results, value objects, signature / canonicalization records) flow into pure
deciders and across the FCIS boundary; a mutable one breaks replay determinism
the same way a mutable aggregate value would. The whole port corpus was frozen by
discipline before this test; now it is enforced.

## runtime_checkable matches isinstance usage

A port Protocol carries `@runtime_checkable` iff some `isinstance` / `issubclass`
check targets it (across src AND tests). The decorator exists only to enable those
checks: decorating a port nothing checks is dead, and checking an undecorated
Protocol raises `TypeError` at runtime. So the decorated-port set must equal the
isinstance-checked-port set. The src+tests scan keeps a conformance check that
lives in `tests/` from being read as "unused".
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files, tracked_test_files

if TYPE_CHECKING:
    from pathlib import Path

_NON_PORT_FILES: frozenset[str] = frozenset({"__init__.py", "errors.py", "value_types.py"})


def _port_files() -> list[Path]:
    return sorted(
        path
        for path in tracked_python_files()
        if "/ports/" in str(path).replace("\\", "/") and path.name not in _NON_PORT_FILES
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _is_protocol_base(base: ast.expr) -> bool:
    return (isinstance(base, ast.Name) and base.id == "Protocol") or (
        isinstance(base, ast.Attribute) and base.attr == "Protocol"
    )


def _protocol_classes(tree: ast.AST) -> list[str]:
    return [
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.ClassDef) and any(_is_protocol_base(b) for b in node.bases)
    ]


def _frozen_dataclass_violations(tree: ast.AST) -> list[str]:
    """One message per `@dataclass` decorator that is not `frozen=True`."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
                violations.append(f"line {decorator.lineno}: {node.name} uses bare @dataclass")
                continue
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else None
            )
            if name != "dataclass":
                continue
            frozen_kw = next((kw for kw in decorator.keywords if kw.arg == "frozen"), None)
            if frozen_kw is None or not (
                isinstance(frozen_kw.value, ast.Constant) and frozen_kw.value.value is True
            ):
                violations.append(f"line {decorator.lineno}: {node.name} is not frozen=True")
    return violations


@pytest.mark.architecture
@pytest.mark.parametrize("path", _port_files(), ids=_qualified)
def test_port_dataclasses_are_frozen(path: Path) -> None:
    """Every `@dataclass` in a port file declares frozen=True."""
    violations = _frozen_dataclass_violations(ast.parse(path.read_text()))
    assert not violations, (
        f"{_qualified(path)} contains non-frozen dataclass(es):\n  "
        + "\n  ".join(violations)
        + "\nPort DTOs flow into pure deciders and must be immutable."
    )


def _runtime_checkable_classes(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for d in node.decorator_list:
            name = d.attr if isinstance(d, ast.Attribute) else getattr(d, "id", None)
            if name == "runtime_checkable":
                out.add(node.name)
    return out


def _runtime_check_targets(tree: ast.AST) -> set[str]:
    """Class names used as the 2nd arg of isinstance()/issubclass() (single or tuple)."""
    targets: set[str] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"isinstance", "issubclass"}
            and len(node.args) >= 2
        ):
            continue
        second = node.args[1]
        elts = second.elts if isinstance(second, ast.Tuple) else [second]
        for elt in elts:
            if isinstance(elt, ast.Name):
                targets.add(elt.id)
            elif isinstance(elt, ast.Attribute):
                targets.add(elt.attr)
    return targets


@pytest.mark.architecture
def test_port_runtime_checkable_matches_isinstance_usage() -> None:
    """A port is @runtime_checkable iff an isinstance/issubclass check targets it."""
    port_protocols: set[str] = set()
    decorated: set[str] = set()
    for path in _port_files():
        tree = ast.parse(path.read_text())
        protos = set(_protocol_classes(tree))
        port_protocols |= protos
        decorated |= _runtime_checkable_classes(tree) & protos

    checked: set[str] = set()
    for path in tracked_python_files() | tracked_test_files():
        text = path.read_text()
        if "isinstance" not in text and "issubclass" not in text:
            continue
        checked |= _runtime_check_targets(ast.parse(text))
    checked_ports = checked & port_protocols

    decorated_but_unchecked = sorted(decorated - checked_ports)
    checked_but_undecorated = sorted(checked_ports - decorated)
    assert not decorated_but_unchecked and not checked_but_undecorated, (
        "Port @runtime_checkable must match isinstance/issubclass usage.\n"
        f"  decorated but never isinstance-checked (dead decorator, remove it): "
        f"{decorated_but_unchecked}\n"
        f"  isinstance-checked but NOT @runtime_checkable (TypeError at runtime, add it): "
        f"{checked_but_undecorated}\n"
        "Decorate a port iff a conformance check targets it; the scan covers src AND tests."
    )
