"""Fitness guard: 2-BM's techniques.md cannot call an AUTHORED Method pending.

`docs/deployments/2-bm/techniques.md` is hand-authored intent prose (unlike the
generated `beamline.md`). When a technique was cited as "a new Method, pending
(TECH-1)" and that Method is later authored into the catalog (the
operations-layer re-derivation Lock 1), the page rots: it describes a future
that already arrived.

This guard catches that specific drift. A table row is STALE when it both:
  - cites a backtick method slug that now exists in `catalog/catalog.yaml`, and
  - frames that row as not-yet-real (pending / "new Method" / "not yet in
    catalog" / a bare TECH-tag).

The further 93 beamlines this guard used to cover (each with its own
techniques.md, merged into a since-retired notes.md) moved to the private
xmap/descriptors repo; cora's test suite no longer iterates over them (see
project_beamline_seeder_design's reasoning: a drift guard only earns its keep
against data cora's own commits can still change). 2-BM is the one deployment
left, and the one whose techniques.md cora keeps editing.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_TECHNIQUES = _REPO_ROOT / "docs" / "deployments" / "2-bm" / "techniques.md"
_CATALOG = _REPO_ROOT / "catalog" / "catalog.yaml"

# A row is framed not-yet-real when it carries one of these phrases.
_PENDING_PHRASE = re.compile(
    r"pending|new Method|not yet in (the )?catalog|Method not yet|not in (the )?catalog",
    re.IGNORECASE,
)
_SLUG = re.compile(r"`([a-z][a-z0-9_]+)`")


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


catalog_descriptor = _load("catalog_descriptor")


def _catalog_methods() -> set[str]:
    return {m.name for m in catalog_descriptor.load(_CATALOG).methods}


def _stale_slugs() -> set[str]:
    """Every authored-method-slug whose 2-BM techniques.md row is stale."""
    methods = _catalog_methods()
    stale: set[str] = set()
    for line in _TECHNIQUES.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or not _PENDING_PHRASE.search(line):
            continue
        for slug in _SLUG.findall(line):
            if slug in methods:
                stale.add(slug)
    return stale


def test_techniques_page_discovered() -> None:
    assert _TECHNIQUES.is_file(), "docs/deployments/2-bm/techniques.md not found"


def test_no_stale_technique_rows() -> None:
    stale = sorted(_stale_slugs())
    assert not stale, (
        "2-bm/techniques.md row(s) call a Method 'pending' / 'new' / 'not in catalog' that now "
        f"EXISTS in catalog/catalog.yaml. Drop the pending framing: {stale}"
    )
