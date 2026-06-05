"""`make_inmemory_kernel(...)` may not be called from production code
outside its own definition module.

`make_inmemory_kernel` builds a `Kernel` with `pool=None` (the
in-memory test-shaped variant). Every cross-aggregate guard that
short-circuits on `pool=None` (install_asset, decommission_asset,
register_fixture as of slice 3a) silently disables when the running
Kernel has no pool. The intent is: only production-test-environment
plumbing in `cora.infrastructure.deps` reaches for this primitive,
and only tests call it directly.

If a future production module accidentally wires the in-memory
primitive (alternate entrypoint, MCP-only deployment, lazy-pool
refactor, etc.), every cross-aggregate guard that relies on the
pool=None short-circuit convention silently disables with zero test
failure. This fitness catches the regression at CI before such a
module can land.

See the project-memory feedback note
`feedback_pool_none_short_circuit_rule_of_three.md` for the
rule-of-three trigger that motivated this test.

## Allowed call sites

  - `src/cora/infrastructure/deps.py`: the definition module. The
    `build_kernel` test-environment branch inside this file is the
    single production caller; tach + this fitness keep the allowance
    scoped.
  - Any path under `tests/`: test wrappers (`tests/unit/_helpers.py`),
    `test_deps.py`'s exercise of the override seams, agent seed
    tests that want full programmatic control over the in-memory
    kernel they hand to `Subscriber.attach`.

Adding a new production callsite requires a deliberate allowlist
edit + a justification comment; the test fails loud otherwise.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_python_files, tracked_test_files

# tests/architecture/<file>.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]

# The one production file allowed to call `make_inmemory_kernel(...)`.
# Test-side files are allowed in bulk via the `_under_tests` check
# below; only explicit production allowances live in the set.
_PRODUCTION_ALLOWLIST: frozenset[str] = frozenset(
    {
        "src/cora/infrastructure/deps.py",
    }
)


def _python_files() -> list[Path]:
    """All git-tracked Python files under src/ and tests/.

    Enumerates from git's tracked-file set rather than `rglob` so a
    half-staged refactor (an existing make_inmemory_kernel(...) call
    edited-then-stashed, a new call site untracked) does not false-fail
    under pre-commit.
    """
    return sorted(tracked_python_files() | tracked_test_files())


def _candidate_files() -> list[Path]:
    """Files that mention `make_inmemory_kernel(` (cheap textual heuristic).

    The trailing `(` skips bare imports and docstring mentions; the AST
    scan inside the parametrized test confirms each candidate has a
    real call expression.
    """
    return [p for p in _python_files() if "make_inmemory_kernel(" in p.read_text()]


def _qualified(p: Path) -> str:
    return str(p.relative_to(_API_ROOT))


def _under_tests(qualified: str) -> bool:
    return qualified.startswith("tests/")


def _make_inmemory_kernel_call_lines(tree: ast.AST) -> list[int]:
    """Find every Call node whose func is a bare `Name("make_inmemory_kernel")`.

    Catches `make_inmemory_kernel(...)` and any keyword-argument form.
    Does not catch a namespaced `cora.infrastructure.deps.make_inmemory_kernel(...)`
    (Attribute form); that form is unused today and would still fail
    tach's import contract if added in a forbidden module.
    """
    lines: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "make_inmemory_kernel"
        ):
            lines.append(node.lineno)
    return lines


@pytest.mark.architecture
@pytest.mark.parametrize("py_file", _candidate_files(), ids=_qualified)
def test_make_inmemory_kernel_called_only_in_allowed_sites(py_file: Path) -> None:
    qualified = _qualified(py_file)
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    lines = _make_inmemory_kernel_call_lines(tree)

    if qualified in _PRODUCTION_ALLOWLIST:
        # Allowlisted production file MUST still call make_inmemory_kernel;
        # otherwise the allowlist is stale and should be pruned.
        assert lines, (
            f"{qualified} is allowlisted but no longer calls "
            f"make_inmemory_kernel(). Prune the allowlist in "
            f"{Path(__file__).name}."
        )
        return

    if _under_tests(qualified):
        # Test-side callers are allowed in bulk. Nothing to assert.
        return

    assert not lines, (
        f"{qualified}: production code calls make_inmemory_kernel(...) "
        f"at line(s) {sorted(lines)}. make_inmemory_kernel builds a "
        f"Kernel with pool=None, which silently disables every "
        f"cross-aggregate guard that short-circuits on pool=None "
        f"(install_asset, decommission_asset, register_fixture, ...). "
        f"Use make_postgres_kernel from cora.infrastructure.deps (or, "
        f"in tests, the build_postgres_deps / build_deps wrappers). "
        f"If this site genuinely needs the in-memory primitive, add it "
        f"to _PRODUCTION_ALLOWLIST with a justification comment."
    )


@pytest.mark.architecture
def test_production_allowlist_files_exist() -> None:
    """Drift catcher: if an allowlisted file moves or is renamed, fail loudly."""
    missing = [rel for rel in _PRODUCTION_ALLOWLIST if not (_API_ROOT / rel).is_file()]
    assert not missing, (
        f"Allowlist references files that no longer exist: {missing}. "
        f"Update the allowlist in {Path(__file__).name}."
    )
