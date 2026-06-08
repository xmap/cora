"""Each BC's routes.py only registers handlers for its own errors,
or for shared-kernel / infrastructure-layer errors.

Sibling of `test_routes_completeness.py`. That test enforces "every
domain error in BC `<bc>` is registered as an HTTP handler in
`cora/<bc>/routes.py`"; this test enforces the converse: "every
error class registered in `cora/<bc>/routes.py` comes from either
`cora.<bc>.*` (the BC's own surface), `cora.shared.*` (pure value-
object construction errors), or `cora.infrastructure.*` (infra-layer
shared errors registered globally by Access)".

Together the pair pins both directions: no orphaned errors,
no cross-BC poaching. A foreign-BC registration is the typical
copy-paste regression — for example wiring `RunNotFoundError`
into `cora/agent/routes.py` because `regenerate_run_debrief` raises it on
the way to deciding. That's the wrong place to map it: the Run
BC owns the 404, and FastAPI's app-scoped handler catches the
exception regardless of which BC's route raised it.

The check is AST-based and covers two registration shapes used
across BCs today:

  1. Direct:  `app.add_exception_handler(SomeError, _handler)`
  2. Looped:  `for cls in (A, B, C): app.add_exception_handler(cls, _handler)`

Names that don't resolve to an import (locally defined classes,
loop-variable identifiers themselves) are skipped — they can't
violate the scope rule.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


def _routes_files() -> dict[str, Path]:
    tracked = tracked_python_files()
    out: dict[str, Path] = {}
    for bc in BCS:
        candidate = CORA_ROOT / bc / "routes.py"
        if candidate in tracked:
            out[bc] = candidate
    return out


def _imports(tree: ast.Module) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                name = alias.asname or alias.name
                out[name] = node.module
    return out


class _Collector(ast.NodeVisitor):
    """Walks one routes.py and collects every class-name reference
    that ends up as the first argument to `add_exception_handler`,
    including names threaded through a `for cls in (A, B, ...):` loop.
    """

    def __init__(self) -> None:
        self.classes: list[str] = []

    def visit_For(self, node: ast.For) -> None:
        loop_var = node.target.id if isinstance(node.target, ast.Name) else None
        if (
            loop_var
            and self._loop_body_registers(node, loop_var)
            and isinstance(node.iter, ast.Tuple)
        ):
            for elt in node.iter.elts:
                if isinstance(elt, ast.Name):
                    self.classes.append(elt.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_exception_handler"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            self.classes.append(node.args[0].id)
        self.generic_visit(node)

    @staticmethod
    def _loop_body_registers(node: ast.For, loop_var: str) -> bool:
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "add_exception_handler"
                and sub.args
                and isinstance(sub.args[0], ast.Name)
                and sub.args[0].id == loop_var
            ):
                return True
        return False


def _is_in_scope(bc: str, module: str) -> bool:
    return (
        module == f"cora.{bc}"
        or module.startswith(f"cora.{bc}.")
        or module.startswith("cora.infrastructure")
        or module.startswith("cora.shared")
    )


@pytest.mark.architecture
def test_routes_only_register_own_bc_or_infra_errors() -> None:
    """Foreign-BC error registrations are the smell this test catches.

    A handler registered here for `cora.run.aggregates.run.RunNotFoundError`
    inside `cora/agent/routes.py` means the Agent BC is presuming to
    HTTP-map Run's domain error. FastAPI's app-scoped handler does the
    right thing without it; the registration is dead weight at best and
    a precedent for cross-BC coupling at worst.
    """
    violations: list[str] = []
    for bc, path in sorted(_routes_files().items()):
        tree = ast.parse(path.read_text())
        imports = _imports(tree)
        collector = _Collector()
        collector.visit(tree)
        for cls in sorted(set(collector.classes)):
            source = imports.get(cls)
            if source is None:
                continue
            if not _is_in_scope(bc, source):
                violations.append(f"cora/{bc}/routes.py: {cls} imported from {source}")
    assert not violations, (
        "Foreign error classes registered as HTTP handlers in a BC that "
        "doesn't own them:\n"
        + "\n".join(f"  - {v}" for v in violations)
        + "\n\nMove the registration to the owning BC's routes.py, or "
        "(if the error is genuinely cross-BC infrastructure) re-home it "
        "under cora.infrastructure.* or cora.shared.*."
    )
