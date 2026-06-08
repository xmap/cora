"""BOUNDED_CONTEXTS frozenset stays in sync with the BC directory tree.

`scripts/scenarios_meta.py` exports a CapitalCase BOUNDED_CONTEXTS
frozenset that two consumers rely on:
  - scenario header validation (tests/integration/scenarios/conftest.py)
  - the docs scenarios-registry page hook

Both treat a missing BC as a coverage gap signal, but neither catches
the inverse drift: a new BC ships under `apps/api/src/cora/<bc>/` and
nobody adds it to BOUNDED_CONTEXTS, so the next scenario test for that
BC trips ScenarioHeaderError. Federation BC drifted exactly that way
(shipped 2026-05-30/31, not added to the registry until 2026-06-01).

This test diffs BOUNDED_CONTEXTS against the actual git-tracked BC
directory list and fails loudly with both missing and extra entries
on either side, so the registry stays honest as BCs land or are
renamed.
"""

from __future__ import annotations

import importlib.util
import sys
from typing import TYPE_CHECKING

import pytest

from .conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from types import ModuleType

_REPO_ROOT = CORA_ROOT.parents[3]
_SCENARIOS_META_PATH = _REPO_ROOT / "scripts" / "scenarios_meta.py"

# Entries under cora/ that are NOT bounded contexts.
_NON_BC_ENTRIES: frozenset[str] = frozenset({"api", "infrastructure", "shared"})


def _load_scenarios_meta() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scenarios_meta", _SCENARIOS_META_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load scenarios_meta from {_SCENARIOS_META_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("scenarios_meta", module)
    spec.loader.exec_module(module)
    return module


def _actual_bc_directories() -> frozenset[str]:
    """First path segment under `cora/` for every tracked .py file."""
    segments: set[str] = set()
    for path in tracked_python_files():
        try:
            rel = path.relative_to(CORA_ROOT)
        except ValueError:
            continue
        if not rel.parts:
            continue
        first = rel.parts[0]
        if first.startswith("_") or first in _NON_BC_ENTRIES:
            continue
        if first.endswith(".py"):
            continue
        segments.add(first)
    return frozenset(segments)


@pytest.mark.architecture
def test_bounded_contexts_match_bc_directory() -> None:
    registry = {bc.lower() for bc in _load_scenarios_meta().BOUNDED_CONTEXTS}
    actual = _actual_bc_directories()

    missing_from_registry = sorted(actual - registry)
    extra_in_registry = sorted(registry - actual)

    if missing_from_registry or extra_in_registry:
        raise AssertionError(
            "scripts/scenarios_meta.py BOUNDED_CONTEXTS diverged from "
            "apps/api/src/cora/ BC directories:\n"
            f"  missing from registry (new BCs to add): {missing_from_registry}\n"
            f"  extra in registry (renamed or removed): {extra_in_registry}\n"
            f"  registry: {sorted(registry)}\n"
            f"  actual:   {sorted(actual)}"
        )
