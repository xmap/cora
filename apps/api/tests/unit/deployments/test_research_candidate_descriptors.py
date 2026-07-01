"""Loader-validation guard for research candidate beamline descriptors.

The Tier-2 research artifacts at research/*/beamlines/*/beamline.candidate.yaml
are drafted to "self-validate against the loader" (research/WORKFLOW.md step 3),
but nothing enforced it: the deployment descriptor test globs
deployments/*/beamline.yaml only. That gap let candidate descriptors drift out
of loader conformance and ship broken (a stage-enum value the loader rejects; a
flat device list where the loader expects stage-grouped subsystems; missing the
maturity/evidence/coverage badges the Beamline model now requires). This test
closes the gap: every git-tracked candidate must load through the same
scripts/beamline_descriptor.py the docs build uses.

Scope is deliberately loader-schema conformance, NOT the deeper catalog
cross-checks the deployment test also runs (model/family resolution). Research
candidates carry new:true / confirm devices and loose families by design; a
clean load is the right bar for a Tier-2 artifact.

The scripts/ module is loaded via importlib (the same dynamic-import bridge as
test_beamline_descriptor.py), and candidates are discovered from git-tracked
files (not a filesystem scan) so half-staged drafts stay invisible during
pre-commit hook runs, mirroring tests/architecture/conftest.py.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bd = _load("beamline_descriptor")


@cache
def _research_candidates() -> list[Path]:
    # Git-tracked candidate descriptors only. A filesystem scan would see
    # half-staged drafts during pre-commit (which stashes only tracked-file
    # edits), so enumerate from git's index, stripping pre-commit's GIT_DIR /
    # GIT_INDEX_FILE so the worktree's real tracked set shows through. Same
    # rationale as tests/architecture/conftest.py's tracked_python_files().
    env = {k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_INDEX_FILE"}}
    result = subprocess.run(
        ["git", "ls-files", "research"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return sorted(
        _REPO_ROOT / line
        for line in result.stdout.splitlines()
        if line.endswith("beamline.candidate.yaml")
    )


def test_at_least_one_research_candidate_descriptor_found() -> None:
    # The load check below is parametrized over discovered candidates; an empty
    # glob would make it vanish and pass vacuously.
    assert _research_candidates(), (
        "no research/*/beamlines/*/beamline.candidate.yaml found in git-tracked files"
    )


@pytest.mark.parametrize(
    "candidate_path",
    _research_candidates(),
    ids=lambda p: f"{p.parents[2].name}/{p.parent.name}",
)
def test_research_candidate_descriptor_loads(candidate_path: Path) -> None:
    # Must load through the real loader without DescriptorError, the
    # self-validation the research WORKFLOW requires of every candidate.
    descriptor = bd.load(candidate_path)
    rel = candidate_path.relative_to(_REPO_ROOT)
    assert descriptor.beamline.name, f"{rel}: missing beamline.name"
    assert descriptor.beamline.facility, f"{rel}: missing beamline.facility"
