"""Architecture fitness: every `_ToolResult` MUST mirror its sibling `Response`.

The conduct verb-family (`conduct_procedure`, `conduct_or_hold_procedure`,
`conduct_from_procedure`, `conduct_until_converged`, `conduct_until_advised`,
`conduct_until_advised_from`) is the one place in this tree where the MCP tool
does not return its slice's REST response model directly; instead each
`tool.py` hand-declares a `_ToolResult` Pydantic class and hand-copies fields
from the `route.py` `*Response` into it, because the MCP tool-output schema
wants a plain `dict` for `failure` where the REST response nests a typed
`ConductorFailureResponse`. Every `_ToolResult` docstring says, in so many
words, "MCP-shape mirror of `<X>Response>`".

That hand-copy is exactly the field-drop shape that shipped in #740:
`conduct_procedure`'s own `_ToolResult` omitted `substrate_writes` for a full
cycle after the REST route gained it, discovered only by reading the file
directly. This is the guard that would have caught it: no test compared the
two field sets, so a field could be added to one and not the other with a
fully green suite. See [[project_field_drop_bug_class]].

## What is checked

For every `tool.py` under `cora.operation.features.*` that defines a
`_ToolResult` class, locate the sibling `route.py` in the same slice
directory and its `*Response` class (by construction there is exactly one
per file today; a second would make "the sibling response" ambiguous and
this test would need to be told which one). Assert the two classes declare
the SAME field names. Types may differ (that is the reason `_ToolResult`
exists at all: `dict[str, Any]` on the MCP side vs a typed sub-model on the
REST side for `failure`); only the field NAMES are compared.

This ranges over whatever slices exist today by walking the filesystem, not
a hardcoded list, so a new `_ToolResult`-pattern slice is covered for free
and a renamed/removed slice cannot leave a stale entry behind.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FEATURES_ROOT = _REPO_ROOT / "apps" / "api" / "src" / "cora" / "operation" / "features"


def _class_field_names(path: Path, class_name: str) -> frozenset[str]:
    """Top-level annotated field names of `class_name` in the module at `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return frozenset(
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            )
    msg = f"no `class {class_name}` found in {path}"
    raise AssertionError(msg)


def _response_class_name(route_path: Path) -> str:
    """The sole top-level class in `route.py` whose name ends `Response`."""
    tree = ast.parse(route_path.read_text(encoding="utf-8"), filename=str(route_path))
    candidates = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name.endswith("Response")
    ]
    assert len(candidates) == 1, (
        f"{route_path} must declare exactly one top-level `*Response` class for this "
        f"test to compare against; found {candidates or 'none'}"
    )
    return candidates[0]


def _slices_with_tool_result() -> list[Path]:
    return sorted(_FEATURES_ROOT.glob("*/tool.py"), key=lambda p: p.parent.name)


@pytest.mark.architecture
def test_every_tool_result_has_the_same_fields_as_its_response() -> None:
    """`_ToolResult` and its sibling `*Response` must declare the same field names."""
    violations: list[str] = []
    checked = 0
    for tool_path in _slices_with_tool_result():
        tool_src = tool_path.read_text(encoding="utf-8")
        if "class _ToolResult" not in tool_src:
            continue
        route_path = tool_path.parent / "route.py"
        assert route_path.exists(), f"{tool_path} defines _ToolResult but has no sibling route.py"
        response_name = _response_class_name(route_path)
        tool_fields = _class_field_names(tool_path, "_ToolResult")
        response_fields = _class_field_names(route_path, response_name)
        checked += 1
        if tool_fields != response_fields:
            missing_from_tool = response_fields - tool_fields
            extra_on_tool = tool_fields - response_fields
            detail: list[str] = []
            if missing_from_tool:
                detail.append(f"missing from _ToolResult: {sorted(missing_from_tool)}")
            if extra_on_tool:
                detail.append(f"present on _ToolResult only: {sorted(extra_on_tool)}")
            violations.append(f"  - {tool_path.parent.name}: " + "; ".join(detail))
    assert checked > 0, (
        "No `_ToolResult` class found under cora.operation.features -- if the "
        "conduct verb-family's MCP tools were renamed or restructured, update "
        "this test's discovery instead of leaving it silently checking nothing."
    )
    assert not violations, (
        "A `_ToolResult` no longer mirrors its sibling `*Response`. See "
        "[[project_field_drop_bug_class]].\n" + "\n".join(violations)
    )
