"""The watched genesis has no operator path in, by construction.

Two structural facts the roadmap's anti-scope depends on, each pinned
here rather than left to convention:

  1. `ConductMode.RECORDED` is constructed in exactly one place: the
     watched-genesis decider. If a second construction site appears
     anywhere under `src/cora`, an operator-reachable path has found a
     way to claim RECORDED, which is precisely the laundering hole the
     axis exists to close.
  2. The in-process-only slices (`observe_enclosure_status`,
     `record_watched_run`) expose zero REST routes and zero MCP tools.
     Their `route.py` / `tool.py` modules are stubs by design; this
     confirms the stub actually stays empty rather than trusting the
     docstring that says so.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_IN_PROCESS_ONLY_SLICES: tuple[str, ...] = (
    "enclosure/features/observe_enclosure_status",
    "run/features/record_watched_run",
)


def _find_conduct_mode_recorded_sites() -> list[Path]:
    """Every tracked file under src/cora that references `ConductMode.RECORDED`
    specifically (other aggregates declare their own unrelated `RECORDED`
    members, e.g. `AcquisitionStatus.RECORDED` in the Data BC, so the scan
    must check the attribute's base name, not just the attribute name)."""
    sites: list[Path] = []
    for path in sorted(tracked_python_files()):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover -- defensive
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "RECORDED"
                and isinstance(node.value, ast.Name)
                and node.value.id == "ConductMode"
            ):
                sites.append(path)
                break
    return sites


@pytest.mark.architecture
def test_conduct_mode_recorded_has_exactly_one_construction_site() -> None:
    sites = _find_conduct_mode_recorded_sites()
    relative = sorted(str(p.relative_to(CORA_ROOT)) for p in sites)
    assert relative == ["run/features/record_watched_run/decider.py"], (
        "ConductMode.RECORDED must be constructed in exactly one place "
        f"(the watched-genesis decider); found it referenced in: {relative}. "
        "A second site is an operator-reachable path claiming a watched "
        "genesis, the exact laundering hole this axis exists to close."
    )


def _slice_route_module(slice_path: str) -> ast.Module:
    path = CORA_ROOT / slice_path / "route.py"
    return ast.parse(path.read_text(encoding="utf-8"))


def _slice_tool_module(slice_path: str) -> ast.Module:
    path = CORA_ROOT / slice_path / "tool.py"
    return ast.parse(path.read_text(encoding="utf-8"))


@pytest.mark.architecture
@pytest.mark.parametrize("slice_path", _IN_PROCESS_ONLY_SLICES)
def test_in_process_only_slice_route_module_declares_no_endpoints(slice_path: str) -> None:
    """No `@router.<verb>(...)` decorator anywhere in the stub route module."""
    tree = _slice_route_module(slice_path)
    decorated_routes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        for dec in node.decorator_list
        if isinstance(dec, ast.Call)
        and isinstance(dec.func, ast.Attribute)
        and isinstance(dec.func.value, ast.Name)
        and dec.func.value.id == "router"
    ]
    assert decorated_routes == [], (
        f"{slice_path}/route.py declares a route decorator, but this slice is "
        "in-process-only by design. If a real endpoint is intended, remove it "
        "from _IN_PROCESS_ONLY_SLICES; otherwise delete the route."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("slice_path", _IN_PROCESS_ONLY_SLICES)
def test_in_process_only_slice_tool_module_register_is_a_no_op(slice_path: str) -> None:
    """`register()`'s body never calls an MCP tool-registration decorator
    or `mcp.tool`/`mcp.add_tool`-shaped call."""
    tree = _slice_tool_module(slice_path)
    register_fn = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "register"
        ),
        None,
    )
    assert register_fn is not None, f"{slice_path}/tool.py has no register() function"
    tool_registration_calls = [
        node
        for node in ast.walk(register_fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"tool", "add_tool"}
    ]
    assert tool_registration_calls == [], (
        f"{slice_path}/tool.py's register() calls an MCP tool-registration "
        "method, but this slice is in-process-only by design."
    )
