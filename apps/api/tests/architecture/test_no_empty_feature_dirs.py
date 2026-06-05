"""No feature directory may exist on disk without any git-tracked file.

Catches the rename-leftover shape: a slice gets renamed
(`enter_maintenance` -> `enter_asset_maintenance`), the old
directory survives on disk only because `__pycache__` keeps it
non-empty for `os.rmdir`, and `git ls-files` shows it gone --
so `test_slice_contract.py` (which enumerates from the tracked
set) cannot see it. Filesystem-level `ls` then makes slice counts
and module docs misleading.

This fitness scans `<bc>/features/` from the filesystem and
fails on any direct subdirectory that holds zero git-tracked
files. Untracked-but-in-flight slices (one staged `__init__.py`)
pass; pure cruft fails.
"""

from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files


def _feature_subdirs() -> list[Path]:
    dirs: list[Path] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        if not features.is_dir():
            continue
        for child in sorted(features.iterdir()):
            if not child.is_dir():
                continue
            if child.name == "__pycache__":
                continue
            if child.name.startswith("_"):
                continue
            dirs.append(child)
    return dirs


def _qualified(slice_dir: Path) -> str:
    rel = slice_dir.relative_to(CORA_ROOT)
    return "cora." + ".".join(rel.parts)


@pytest.mark.architecture
@pytest.mark.parametrize("slice_dir", _feature_subdirs(), ids=_qualified)
def test_feature_dir_contains_a_tracked_file(slice_dir: Path) -> None:
    tracked_here = {p for p in tracked_python_files() if p.parent == slice_dir}
    assert tracked_here, (
        f"{_qualified(slice_dir)}: directory exists on disk but git tracks no "
        f"file inside it. Almost certainly a rename leftover -- delete the dir "
        f"(stale __pycache__ is keeping it alive)."
    )
