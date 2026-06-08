"""Single-source canonicalizer fitness.

Per [[project-run-procedure-replay-design]] §Canonical-JSON
consolidation + §Locks.  had three copies of the inline
`json.dumps(..., sort_keys=True, separators=(",", ":"))` string
(decider's bindings/steps hashing, events.py to_payload arm, and the
contract test).  consolidated to one source:
`cora.shared.canonical_json.canonical_json_bytes`.

This fitness AST-walks `tracked_python_files()` (per
[[feedback-architecture-test-git-aware]]) under the operation and
recipe BC source trees only, and asserts every `json.dumps` Call
node carrying `sort_keys=True` lives in the single allowlisted file
(`canonical_json.py` itself). Pre-existing co-occurrences in
`shared/content_hash.py`, `infrastructure/idempotency.py`,
and the  integration test stay out of scope because they
canonicalize for orthogonal purposes (content-addressed identity +
idempotency keys); promoting them to canonical_json_bytes is a
future rule-of-three hoist, not a  lock.

A future refactor that inlines `json.dumps(sort_keys=True)` anywhere
under cora/operation or cora/recipe fails this test and is steered
back to `canonical_json_bytes`.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

# Source trees this fitness governs. Other BC trees + infrastructure +
# shared + tests carry their own canonicalizers (deliberately
# untouched in ; rule-of-three deferred). Restrict the AST walk
# so the scope of the lock is unambiguous.
_SCOPED_TREES = (
    CORA_ROOT / "operation",
    CORA_ROOT / "recipe",
)

# The single file allowed to construct `json.dumps(..., sort_keys=True)`
# in scope. `canonical_json_bytes` is hoisted to cora/shared (NOT in
# scope here); both `cora/operation/` and `cora/recipe/` import it from
# there. If a future module legitimately needs to extend the
# canonicalizer (e.g., add a `decimal=str` mode), add it here AND in
# the comment block at the top of canonical_json.py.
# No source file under cora/operation or cora/recipe is allowed to call
# json.dumps with sort_keys=True directly. The allowlist is intentionally
# empty: the helper lives at cora.shared.canonical_json (out of
# scope of this fitness's tree filter).
_ALLOWLIST_RELATIVE_PATHS: frozenset[Path] = frozenset()


def _scoped_files() -> list[Path]:
    files: list[Path] = []
    for path in tracked_python_files():
        if any(path.is_relative_to(tree) for tree in _SCOPED_TREES):
            files.append(path)
    return sorted(files)


def _json_dumps_sort_keys_lines(path: Path) -> list[int]:
    tree = ast.parse(path.read_text())
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match both `json.dumps(...)` and bare `dumps(...)` (if someone
        # ever `from json import dumps`d into the scoped trees).
        is_json_dumps = (
            isinstance(func, ast.Attribute)
            and func.attr == "dumps"
            and isinstance(func.value, ast.Name)
            and func.value.id == "json"
        ) or (isinstance(func, ast.Name) and func.id == "dumps")
        if not is_json_dumps:
            continue
        for kw in node.keywords:
            if (
                kw.arg == "sort_keys"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
            ):
                hits.append(node.lineno)
                break
    return hits


@pytest.mark.architecture
def test_canonical_json_bytes_is_the_single_source_in_operation_and_recipe_trees() -> None:
    """No source file under `cora/operation/` or `cora/recipe/` may
    invoke `json.dumps(..., sort_keys=True, ...)` directly: route all
    canonical-JSON byte production through
    `cora.shared.canonical_json.canonical_json_bytes`."""
    violations: list[str] = []
    for path in _scoped_files():
        relative = path.relative_to(CORA_ROOT)
        if relative in _ALLOWLIST_RELATIVE_PATHS:
            continue
        lines = _json_dumps_sort_keys_lines(path)
        for line in lines:
            violations.append(f"  {relative}:{line}")
    assert not violations, (
        "Inline `json.dumps(..., sort_keys=True)` co-occurrence found in "
        "the operation/recipe BC source trees; route the call through "
        "`cora.shared.canonical_json.canonical_json_bytes` so "
        "hash bytes stay byte-equal across write-time and replay-time. "
        "See [[project-run-procedure-replay-design]] §Canonical-JSON "
        "consolidation. Offenders:\n" + "\n".join(violations)
    )
