"""Enforcement: no in-process call site may pass the NIL sentinel as `surface_id`.

`NIL_SENTINEL_ID` (`UUID(int=0)`) resolves to the FRONT Policy in Authorize.
A background runtime that authorizes with `surface_id=NIL_SENTINEL_ID` gets
strict-denied at the surface check instead of matching the in-process door
(`SYSTEM_IN_PROCESS_SURFACE_ID`). This is the enforcement blocker the
`watcher-door-sweep` work fixes: every watcher, subscriber, and background
push loop that authorizes in-process now passes
`surface_id=SYSTEM_IN_PROCESS_SURFACE_ID`.

`NIL_SENTINEL_ID` legitimately remains the value for `conduit_id=` at these
same call sites (no HTTP/MCP conduit exists for a background runtime); this
test checks only the `surface_id=` keyword, never `conduit_id=`.

AST walk, not grep: a grep for the literal string `NIL_SENTINEL_ID` would
also match the docstring in `cora.api.in_process_grants` that quotes the
grep command used to find these sites during the sweep. An AST walk only
ever inspects `ast.keyword` argument bindings, so a docstring's string
constant is never mistaken for a keyword argument.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

# Call sites where `surface_id=NIL_SENTINEL_ID` is a deliberate, reviewed
# exception rather than an oversight. Expected to stay empty: every
# in-process authorize() call site found during the sweep had a real
# in-process surface available.
_ALLOWED_NIL_SURFACE_SITES: frozenset[str] = frozenset()


def _cora_files() -> list[Path]:
    return sorted(p for p in tracked_python_files() if p.is_relative_to(CORA_ROOT))


def _qualified(file: Path) -> str:
    rel = file.relative_to(CORA_ROOT)
    return "cora." + ".".join(rel.with_suffix("").parts)


def _nil_surface_id_lines(file: Path) -> list[int]:
    """Line numbers of every `surface_id=NIL_SENTINEL_ID` keyword argument
    in one file, found by walking the parsed AST rather than the text."""
    tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword) or node.arg != "surface_id":
            continue
        value = node.value
        if isinstance(value, ast.Name) and value.id == "NIL_SENTINEL_ID":
            lines.append(node.lineno)
    return lines


@pytest.mark.architecture
@pytest.mark.parametrize("file", _cora_files(), ids=_qualified)
def test_no_call_site_passes_nil_sentinel_as_surface_id(file: Path) -> None:
    """No file under `src/cora` may pass `surface_id=NIL_SENTINEL_ID` at a
    keyword argument, unless the exact qualified module name is listed in
    `_ALLOWED_NIL_SURFACE_SITES` with a comment explaining why.

    Passing the NIL sentinel as the arrival Surface strict-denies at the
    Authorize surface check instead of matching a real Policy, which is
    the silent-lockout failure mode this test guards against for every
    background runtime that authorizes in-process."""
    qualified = _qualified(file)
    lines = _nil_surface_id_lines(file)
    if qualified in _ALLOWED_NIL_SURFACE_SITES:
        return
    assert not lines, (
        f"{qualified}: surface_id=NIL_SENTINEL_ID at line(s) {lines}. In-process "
        "call sites must authorize against SYSTEM_IN_PROCESS_SURFACE_ID "
        "(cora.infrastructure.routing), not the NIL sentinel, which strict-denies "
        "at the surface check. If this site genuinely has no in-process surface "
        "available, add its qualified module name to _ALLOWED_NIL_SURFACE_SITES "
        "with a comment explaining why."
    )


@pytest.mark.architecture
def test_cora_files_were_actually_discovered() -> None:
    """Guards the enumerator itself: a broken tracked-files call that
    silently returned nothing would make the parametrized case above
    vacuously pass for every file."""
    files = _cora_files()
    assert len(files) > 500, (
        f"Expected at least 500 tracked .py files under src/cora, found {len(files)}; "
        "tracked_python_files() may be broken or the worktree may be shallow."
    )
