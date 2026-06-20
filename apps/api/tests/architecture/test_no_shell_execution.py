"""No shell-based process execution anywhere under ``src/cora``.

The vetted-launch_spec design (a Method names parameters, the server
renders an argv list, the adapter spawns it with
``asyncio.create_subprocess_exec``) makes command injection a type
fact, not a runtime hope: a parameter value is always exactly one argv
token, never re-parsed by a shell. That guarantee only holds if NOTHING
in the codebase routes execution through a shell. This fitness function
enforces that, banning every shell-exec vector:

- ``shell=True`` on any call (``subprocess.run`` / ``Popen`` /
  ``call`` / ``check_call`` / ``check_output`` / ...)
- ``asyncio.create_subprocess_shell(...)``
- ``os.system(...)`` / ``os.popen(...)``
- ``subprocess.getoutput(...)`` / ``subprocess.getstatusoutput(...)``

The safe spawners (``subprocess.run([...])`` with a list, and
``asyncio.create_subprocess_exec(...)``) are untouched: they pass argv
directly to ``execve`` with no shell in between.

Scoped to git-tracked ``src/cora`` files (see conftest for why
enumeration is git-aware). If a future operational tool genuinely needs
a shell, add it to ``ALLOWLIST`` with a one-line justification rather
than weakening the scan.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

# Module-qualified names (``cora.<...>``) permitted to use a shell.
# Empty by design: nothing in the spine needs one.
ALLOWLIST: frozenset[str] = frozenset()

_SHELL_FUNCS: frozenset[str] = frozenset(
    {"create_subprocess_shell", "system", "popen", "getoutput", "getstatusoutput"}
)


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _called_name(call: ast.Call) -> str | None:
    """The bare function name of a call (``f`` for ``a.b.f(...)`` or ``f(...)``)."""
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _shell_execution_lines(tree: ast.Module) -> list[int]:
    out: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _called_name(node)
        if name in _SHELL_FUNCS:
            out.append(node.lineno)
            continue
        for kw in node.keywords:
            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                out.append(node.lineno)
                break
    return sorted(set(out))


@pytest.mark.architecture
@pytest.mark.parametrize(
    "src_file",
    sorted(tracked_python_files()),
    ids=_qualified,
)
def test_src_file_has_no_shell_execution(src_file: Path) -> None:
    qualified = _qualified(src_file)
    if qualified in ALLOWLIST:
        pytest.skip(f"{qualified} is in ALLOWLIST")
    tree = ast.parse(src_file.read_text(encoding="utf-8"))
    lines = _shell_execution_lines(tree)
    assert not lines, (
        f"{qualified} routes process execution through a shell at "
        f"line(s) {lines}. Shell exec re-parses its argument string, which "
        "reopens the command-injection hole the launch_spec design closes. "
        "Use a list argv with subprocess.run([...]) or "
        "asyncio.create_subprocess_exec(...) instead, or add an ALLOWLIST "
        "entry with justification."
    )


@pytest.mark.architecture
def test_shell_execution_allowlist_entries_exist() -> None:
    """Each ALLOWLIST entry must name a real tracked module (no stale skips)."""
    tracked = {_qualified(p) for p in tracked_python_files()}
    for qualified in ALLOWLIST:
        assert qualified in tracked, (
            f"{qualified}: ALLOWLIST entry no longer names a tracked src/cora module; remove it."
        )
