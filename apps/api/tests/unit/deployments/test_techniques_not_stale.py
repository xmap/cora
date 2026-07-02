"""Fitness guard: a beamline's techniques.md cannot call an AUTHORED Method pending.

The per-beamline `docs/deployments/<id>/techniques.md` pages are hand-authored
intent prose (unlike the generated `beamline.md`). When a technique was cited as
"a new Method, pending (TECH-1)" and that Method is later authored into the
catalog (the operations-layer re-derivation Lock 1), the page rots: it describes
a future that already arrived.

This guard catches that specific drift. A techniques.md table row is STALE when
it both:
  - cites a backtick method slug that now exists in `catalog/catalog.yaml`, and
  - frames that row as not-yet-real (pending / "new Method" / "not yet in
    catalog" / a bare TECH-tag).

A stale row must be either fixed (drop the pending framing now that the Method
exists) or listed in `_KNOWN_STALE` below. `_KNOWN_STALE` is an enumerated
backlog: the rows already stale when Lock 1 landed, deliberately left for the
in-flight beamline-page redesign to clear (that work regenerates these pages, so
hand-editing them now would churn / collide). The guard's value is catching NEW
drift: a newly-authored Method whose citing page still says pending fails the
build unless explicitly parked here.

Keyed by (beamline, method_slug). Removing an entry once its page is fixed is
required: a _KNOWN_STALE entry that is no longer stale fails the no-dead-entry
check, so the backlog cannot rot silent.
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
_DEPLOYMENTS_DOCS = _REPO_ROOT / "docs" / "deployments"
_CATALOG = _REPO_ROOT / "catalog" / "catalog.yaml"

# A row is framed not-yet-real when it carries one of these phrases.
_PENDING_PHRASE = re.compile(
    r"pending|new Method|not yet in (the )?catalog|Method not yet|not in (the )?catalog",
    re.IGNORECASE,
)
_SLUG = re.compile(r"`([a-z][a-z0-9_]+)`")

# Rows already stale when Lock 1 landed (2026-07-02): the page cites a now-authored
# Method but still frames it pending. Backlog for the beamline-page redesign to
# clear; each removal is verified by the no-dead-entry check below.
_KNOWN_STALE: set[tuple[str, str]] = {
    ("13-id", "powder_diffraction"),
    ("cdi", "ptychography"),
    ("chx", "xpcs"),
    ("cms", "grazing_incidence_scattering"),
    ("esm", "angle_resolved_photoemission"),
    ("faxtor", "radiography"),
    ("fxi", "tomography"),
    ("hex", "radiography"),
    ("hex", "powder_diffraction"),
    ("i13-1", "ptychography"),
    ("id32", "resonant_inelastic_scattering"),
    ("ixs", "inelastic_scattering"),
    ("mogno", "tomography"),
    ("p10", "ptychography"),
    ("pdf", "powder_diffraction"),
    ("six", "resonant_inelastic_scattering"),
}


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


def _stale_rows() -> set[tuple[str, str]]:
    """Every (beamline, authored-method-slug) whose techniques.md row is stale."""
    methods = _catalog_methods()
    stale: set[tuple[str, str]] = set()
    for techniques_md in sorted(_DEPLOYMENTS_DOCS.glob("*/techniques.md")):
        beamline = techniques_md.parent.name
        for line in techniques_md.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| ") or not _PENDING_PHRASE.search(line):
                continue
            for slug in _SLUG.findall(line):
                if slug in methods:
                    stale.add((beamline, slug))
    return stale


def test_techniques_pages_discovered() -> None:
    pages = list(_DEPLOYMENTS_DOCS.glob("*/techniques.md"))
    assert len(pages) >= 80, f"expected the full fleet of techniques.md, found {len(pages)}"


def test_no_new_stale_technique_rows() -> None:
    new_stale = sorted(_stale_rows() - _KNOWN_STALE)
    assert not new_stale, (
        "techniques.md row(s) call a Method 'pending' / 'new' / 'not in catalog' that now "
        "EXISTS in catalog/catalog.yaml. Drop the pending framing now the Method is authored, "
        "or add to _KNOWN_STALE with intent:\n"
        + "\n".join(f"  {bl}: `{slug}`" for bl, slug in new_stale)
    )


def test_no_dead_known_stale_entries() -> None:
    fixed = sorted(_KNOWN_STALE - _stale_rows())
    assert not fixed, (
        "_KNOWN_STALE entr(ies) are no longer stale (page fixed or method removed); "
        f"drop them from the backlog: {fixed}"
    )
