"""Shared roots and helpers for architecture fitness-function tests.

These tests run alongside the rest of the suite (`pytest` picks
them up automatically) but enforce structural invariants the
import graph + AST + filesystem can prove. Tach (`tach.toml` at
the apps/api root) handles dependency-graph rules; everything
under this directory handles the rules tach can't express:
slice file contracts, decider purity, completeness-of-wiring.

`SRC_ROOT` is computed relative to this file so tests work
whether pytest is invoked from `apps/api/` (the Makefile target)
or from the repository root (CI).

## Slice enumeration is git-aware, not filesystem-aware

`tracked_python_files()` returns the set of `.py` files under
`src/cora` that git is tracking. Architecture tests that enumerate
slices MUST filter by this set rather than scan the filesystem
directly. Reason: pre-commit only stashes unstaged changes to
**tracked** files (issues #1212, #708 — maintainer rejected
untracked-stash twice because it would clobber local venvs / tox
state). Untracked files stay live on disk during hook runs. A
filesystem scan therefore sees half-staged slices (untracked
handler.py + stashed wire.py edits hidden) and false-fails
wire-completeness / contract checks. Filtering through git's
tracked-file list mirrors what pre-commit actually evaluates:
new slices in flight stay invisible until `git add`ed, at which
point all the usual invariants kick in.
"""

import os
import subprocess
from functools import cache
from pathlib import Path

# tests/architecture/conftest.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]
# apps/api/ -> repo root -> infra/atlas/migrations
_REPO_ROOT = _API_ROOT.parent.parent
_MIGRATIONS_DIR = _REPO_ROOT / "infra" / "atlas" / "migrations"

SRC_ROOT = _API_ROOT / "src"
CORA_ROOT = SRC_ROOT / "cora"

BCS: tuple[str, ...] = (
    "access",
    "agent",
    "calibration",
    "campaign",
    "caution",
    "data",
    "decision",
    "enclosure",
    "equipment",
    "federation",
    "operation",
    "recipe",
    "run",
    "safety",
    "subject",
    "supply",
    "trust",
)


@cache
def tracked_python_files() -> frozenset[Path]:
    """Absolute paths to git-tracked `.py` files under `src/cora`.

    See module docstring for why architecture fitness functions
    must enumerate from this set rather than from filesystem scans.
    Cached because pytest collection invokes the slice enumerators
    multiple times.
    """
    return _tracked_python_files_under("src/cora")


@cache
def tracked_test_files() -> frozenset[Path]:
    """Absolute paths to git-tracked `.py` files under `tests/`.

    Sibling to `tracked_python_files()`. Same rationale: architecture
    fitness functions that enumerate test-side files (helper-naming
    conventions, kernel-construction sites, subscriber registries that
    live alongside tests) must filter through git's tracked set rather
    than scan the filesystem, because pre-commit only stashes unstaged
    changes to **tracked** files.
    """
    return _tracked_python_files_under("tests")


def _tracked_python_files_under(subdir: str) -> frozenset[Path]:
    # Strip pre-commit's GIT_DIR / GIT_INDEX_FILE env vars: they point at
    # the parent repo's hook-impl staging area and would mask the worktree's
    # actual tracked files. See feedback_worktree_precommit_arch_tests.
    env = {k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_INDEX_FILE"}}
    result = subprocess.run(
        ["git", "ls-files", subdir],
        cwd=_API_ROOT,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return frozenset(
        _API_ROOT / line for line in result.stdout.splitlines() if line.endswith(".py")
    )


@cache
def tracked_migration_files() -> tuple[Path, ...]:
    """Absolute paths to git-tracked `.sql` files under `infra/atlas/migrations/`,
    sorted lexicographically (timestamp-prefixed filenames give chronological order).

    Migration-aware sibling of `tracked_python_files()` and
    `tracked_test_files()`. Tests that fold over migration history must
    use this rather than `_MIGRATIONS_DIR.glob("*.sql")` for the same
    reason: pre-commit only stashes tracked files, and a half-staged
    migration on disk would otherwise leak into the architecture run
    and false-fail the REVOKE / GRANT / projection-table fitness checks.
    Returns a tuple (not a frozenset) because migration order is
    semantically meaningful: ALTER ... RENAME and DROP statements
    discard earlier CREATE entries in the projection-table walker.
    """
    result = subprocess.run(
        ["git", "ls-files", "infra/atlas/migrations"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return tuple(
        sorted(_REPO_ROOT / line for line in result.stdout.splitlines() if line.endswith(".sql"))
    )
