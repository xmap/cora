"""Pin: every Equipment BC aggregate directory carries the same core file set.

Background: the Equipment BC now ships five aggregates (Family,
Asset, Frame, Mount, Model). Earlier aggregates accreted siblings
unevenly (`affordance.py` on Family, `settings_validation.py` on
Family + Asset, `read.py` added late to Model in Commit B). Each
clone reopened the same questions about which files are
load-bearing versus optional. This fitness locks the load-bearing
set so the next clone starts from a checklist rather than a survey.

Rule: every non-private aggregate directory under
`apps/api/src/cora/equipment/aggregates/` MUST track these five
files:

  - __init__.py
  - state.py
  - events.py
  - evolver.py
  - read.py

Optional siblings (allowed but not required) include
`affordance.py`, `settings_validation.py`, or other helpers that
arise from a single aggregate's needs. The fitness deliberately
does not enumerate optional files: the goal is to lock the
*minimum* shared shape, not to forbid divergence above it.

`_drawing.py` and `_placement.py` (private modules at the
`aggregates/` package root) are not aggregate directories and are
ignored. Anything starting with `_` or named `__pycache__` is
skipped ,  the same convention `BC root layout (flat)` uses for
private helpers.

Enumeration is git-aware via `tracked_python_files()` per the
worktree pre-commit-stash rationale in `conftest.py`: untracked
half-staged files must stay invisible to this scan, otherwise
in-flight aggregate skeletons would false-fail before the author
finishes wiring them up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

_AGGREGATES_ROOT = CORA_ROOT / "equipment" / "aggregates"

_REQUIRED_FILES: tuple[str, ...] = (
    "__init__.py",
    "state.py",
    "events.py",
    "evolver.py",
    "read.py",
)


def _aggregate_dirs() -> list[Path]:
    """Aggregate directories under `equipment/aggregates/`.

    A directory qualifies when:
      - it sits directly under `aggregates/`,
      - its name does not start with `_` (private modules like
        `_placement.py` / `_drawing.py` are not aggregates), and
      - it tracks an `__init__.py` (so the scan stays git-aware).

    Returns directories sorted by name for stable parametrize ids.
    """
    tracked = tracked_python_files()
    dirs: set[Path] = set()
    for path in tracked:
        try:
            rel = path.relative_to(_AGGREGATES_ROOT)
        except ValueError:
            continue
        if len(rel.parts) < 2:
            continue
        aggregate_name = rel.parts[0]
        if aggregate_name.startswith("_") or aggregate_name == "__pycache__":
            continue
        if path.name == "__init__.py" and path.parent.parent == _AGGREGATES_ROOT:
            dirs.add(path.parent)
    return sorted(dirs)


@pytest.mark.architecture
@pytest.mark.parametrize("aggregate_dir", _aggregate_dirs(), ids=lambda p: p.name)
def test_equipment_aggregate_carries_required_files(aggregate_dir: Path) -> None:
    """Equipment aggregate must track every file in `_REQUIRED_FILES`."""
    tracked = tracked_python_files()
    missing = [name for name in _REQUIRED_FILES if (aggregate_dir / name) not in tracked]
    assert not missing, (
        f"equipment aggregate `{aggregate_dir.name}` is missing required "
        f"file(s): {', '.join(missing)}.\n"
        f"Every aggregate under {_AGGREGATES_ROOT.relative_to(CORA_ROOT.parent.parent)} "
        f"must track: {', '.join(_REQUIRED_FILES)}.\n"
        "Add the missing module(s) before merging, or, if the aggregate is "
        "genuinely a different shape, justify the divergence in the BC "
        "module doc and update this fitness."
    )
