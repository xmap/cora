"""Fitness guard: pending Method/Capability references stay enumerated, not silent.

A `beamline.yaml` documents the operations a beamline runs by naming the
Method or Capability that models each. When the modelling note references a
technique the catalog does not yet carry, it writes an IOU:

    reusing the pending `xas_spectroscopy` Method

Left unguarded, these IOUs multiply invisibly: an audit of the fleet found
~13 distinct technique slugs referenced this way across most beamline.yaml
files, none of them present in `catalog/catalog.yaml` or in `apps/api/src`.
The operations vocabulary (Capabilities / Methods) had grown against one
deployment while the device vocabulary (Families) grew against the whole
fleet, so the notes promised a model that was never queued.

This guard makes every pending reference explicit. A slug named in a
`pending ... Method` / `pending ... Capability` construct must either:

  - exist in the catalog descriptor (`catalog/catalog.yaml`), meaning the
    IOU has been paid; or
  - appear on `_PENDING_ALLOWLIST` below, an enumerated queue of techniques
    known to be unmodelled, each carrying its disposition.

A new untracked IOU (a slug that is neither in the catalog nor on the
allowlist) fails the build, so the queue cannot silently grow. When a
technique is authored into the catalog, its slug is removed from the
allowlist and the guard confirms the citation now resolves.

The allowlist also cannot rot: every entry must still be referenced by at
least one beamline.yaml (a slug authored into the catalog, or a citation
deleted, leaves a dead allowlist entry the guard rejects).

Disposition tags on each allowlist entry (documentation, not enforced):
  - earned-not-yet-authored: the rule-of-three has fired (3+ deployments
    share the technique, measured by Family binding); authoring lagged.
  - not-yet-earned: fewer than three deployments; stays pending until the
    trigger fires.
  - decompose: too coarse to author as one Method (the generic
    `diffraction` slug); splits into specific capabilities at author time.
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
_DEPLOYMENTS = _REPO_ROOT / "deployments"
_CATALOG = _REPO_ROOT / "catalog" / "catalog.yaml"


def _load(name: str) -> ModuleType:
    # scripts/ is not on the package path; the descriptor is loaded by file,
    # mirroring test_catalog_descriptor.py so the lean docs interpreter (no
    # cora package) can run this guard too.
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


catalog_descriptor = _load("catalog_descriptor")

# The IOU construct: "pending <...> Method(s)" or "pending <...> Capability|Capabilities",
# with zero or more backtick-quoted slugs in the span between "pending" and the kind noun.
_PENDING_SPAN = re.compile(r"pending\s+([^.\n]*?)\b(?:Methods?|Capabilit(?:y|ies))\b")
_SLUG = re.compile(r"`([a-z][a-z0-9_]+)`")

# Enumerated queue of technique slugs referenced as pending but not yet in the
# catalog. Each maps to its disposition (see module docstring). Removing a slug
# here without authoring it into the catalog (or deleting its citation) fails
# the no-dead-entry check; adding an unlisted pending slug fails the coverage
# check. Names here are the slugs AS CITED today; the authoring slice renames
# citations to the convention-checked canonical names as it pays each IOU.
_PENDING_ALLOWLIST: dict[str, str] = {
    # Authored in the catalog under a canonical name (Lock 1); the slug stays
    # only because a beamline.yaml citation still uses the old spelling. These
    # clear when the citation-rewrite sweep renames the reference (then the slug
    # becomes unreferenced and is removed).
    "mx_data_collection": "authored-as-macromolecular_crystallography; citation-rewrite pending",
    "xas_spectroscopy": "authored-as-absorption_spectroscopy; citation-rewrite pending",
    "scanning_fluorescence_microscopy": "authored-as-xray_fluorescence_mapping; rewrite pending",
    "small_angle_scattering": "authored-as-small_wide_angle_scattering; citation-rewrite pending",
    "wide_angle_scattering": "authored-as-small_wide_angle_scattering; citation-rewrite pending",
    "resonant_scattering": "authored-as-resonant_inelastic_scattering; citation-rewrite pending",
    # Genuinely not yet earned (n<3) or deferred; stay pending until authored.
    "magnetic_scattering": "not-yet-earned",
    "total_scattering": "not-yet-earned",
    "energy_dispersive_diffraction": "not-yet-earned",
    "xmcd": "not-yet-earned",
}


def _catalog_slugs() -> set[str]:
    """Method names and Capability code tails carried by the catalog today."""
    cat = catalog_descriptor.load(_CATALOG)
    method_names = {m.name for m in cat.methods}
    capability_tails = {c.code.rsplit(".", 1)[-1] for c in cat.capabilities}
    return method_names | capability_tails


def _pending_references() -> dict[str, set[str]]:
    """Map each cited pending slug to the set of beamlines citing it."""
    refs: dict[str, set[str]] = {}
    for beamline_yaml in sorted(_DEPLOYMENTS.glob("*/beamline.yaml")):
        beamline = beamline_yaml.parent.name
        text = beamline_yaml.read_text(encoding="utf-8")
        for span in _PENDING_SPAN.findall(text):
            for slug in _SLUG.findall(span):
                refs.setdefault(slug, set()).add(beamline)
    return refs


def test_pending_references_are_discovered() -> None:
    # Guards the parser: if the construct or path drifts, the checks below
    # would pass vacuously. The fleet is known to carry pending references.
    assert _pending_references(), (
        "no `pending ... Method/Capability` references parsed from any "
        "deployments/*/beamline.yaml (parser or path drift?)"
    )


def test_every_pending_slug_is_in_catalog_or_allowlisted() -> None:
    known = _catalog_slugs()
    refs = _pending_references()
    untracked = {
        slug: sorted(beamlines)
        for slug, beamlines in refs.items()
        if slug not in known and slug not in _PENDING_ALLOWLIST
    }
    assert not untracked, (
        "beamline.yaml references a pending Method/Capability slug that is "
        "neither in catalog/catalog.yaml nor on _PENDING_ALLOWLIST. Author it "
        "into the catalog, or add it to the allowlist with its disposition:\n"
        + "\n".join(f"  `{slug}` cited by {bls}" for slug, bls in sorted(untracked.items()))
    )


def test_no_dead_allowlist_entries() -> None:
    known = _catalog_slugs()
    refs = _pending_references()
    authored = sorted(slug for slug in _PENDING_ALLOWLIST if slug in known)
    assert not authored, (
        "allowlisted slug(s) now exist in the catalog; remove them from "
        f"_PENDING_ALLOWLIST (the IOU is paid): {authored}"
    )
    unreferenced = sorted(slug for slug in _PENDING_ALLOWLIST if slug not in refs)
    assert not unreferenced, (
        "allowlisted slug(s) no longer cited by any beamline.yaml; remove the "
        f"dead allowlist entr(ies): {unreferenced}"
    )
