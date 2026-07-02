"""Fitness guard: Practices are backed by device-Family coverage (Lock 2).

Realizes Lock 2 of [[project-operations-layer-rederivation-design]]: a Practice
is a Method a beamline can actually run, and "can run" means the beamline's
installed devices cover the Method's `needed_families` contract, the same
set-cover the spine enforces at `define_plan` bind time. The derivation kernel
is `scripts/practice_derivation.py`.

Two guarantees:

  - fleet-wide computability: the derivation runs for every deployment and
    never yields a Method the catalog does not define (the roster is a subset
    of the catalog's Methods, so a renderer or the spine can trust it).
  - bridge integrity: every REAL (non-pending) Practice hand-authored in a
    `site.yaml` names a Method that at least one of that Site's hosted
    beamlines can actually derive (its families cover the Method). A curated
    Practice asserting hardware no hosted beamline models is drift: either the
    beamline's device model is missing hardware, or the Practice is aspirational
    and belongs under `pending:`. Pending Practices are exempt (they ARE the
    acknowledged IOUs).

The bridge check is the point of Lock 2: it makes the operations layer answer
to the whole fleet's device model instead of accreting only where someone
hand-authored a site page.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_DEPLOYMENTS = _REPO_ROOT / "deployments"
_CATALOG = _REPO_ROOT / "catalog" / "catalog.yaml"


def _load(name: str) -> ModuleType:
    # scripts/ is not on the package path; load by file, mirroring
    # test_catalog_descriptor.py so the lean docs interpreter runs this too.
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# catalog_descriptor + beamline_descriptor are imported by practice_derivation
# at module load; register them under their bare names first so its
# `import catalog_descriptor` resolves.
_load("catalog_descriptor")
_load("beamline_descriptor")
_load("site_descriptor")
pderiv = _load("practice_derivation")
catalog_descriptor = sys.modules["catalog_descriptor"]
site_descriptor = sys.modules["site_descriptor"]
beamline_descriptor = sys.modules["beamline_descriptor"]


def _rosters() -> dict[str, Any]:
    # DerivedRoster values; typed Any because practice_derivation is loaded
    # dynamically (scripts/ is off the package path), matching the sibling
    # descriptor tests' handling of importlib-loaded modules.
    rosters: dict[str, Any] = pderiv.derive_all(_DEPLOYMENTS, _CATALOG)
    return rosters


def _facility_of(slug: str) -> str | None:
    descriptor = beamline_descriptor.load(_DEPLOYMENTS / slug / "beamline.yaml")
    return descriptor.beamline.facility


def test_derivation_covers_every_deployment() -> None:
    rosters = _rosters()
    # Guards against discovery drift: a moved path would make the checks below
    # pass vacuously. The fleet is known to be non-trivial.
    assert len(rosters) >= 80, f"expected the full fleet, derived only {len(rosters)} rosters"


def test_derived_rosters_are_catalog_methods() -> None:
    catalog = catalog_descriptor.load(_CATALOG)
    method_names = {m.name for m in catalog.methods}
    rosters = _rosters()
    offenders = {
        slug: sorted(set(roster.practiceable) - method_names)
        for slug, roster in rosters.items()
        if not (set(roster.practiceable) <= method_names)
    }
    assert not offenders, (
        f"derived roster contains a Method the catalog does not define (kernel drift): {offenders}"
    )


def test_real_site_practices_are_hardware_backed() -> None:
    rosters = _rosters()
    site_derivable: dict[str, set[str]] = {}
    for slug, roster in rosters.items():
        facility = _facility_of(slug)
        if facility is None:
            continue
        site_derivable.setdefault(facility, set()).update(roster.practiceable)

    unbacked: list[str] = []
    for site_yaml in sorted(_DEPLOYMENTS.glob("*/site.yaml")):
        site = site_descriptor.load(site_yaml)
        site_slug = site_yaml.parent.name
        derivable = site_derivable.get(site_slug, set())
        for practice in site.practices:
            if practice.pending:
                continue
            if practice.method and practice.method not in derivable:
                unbacked.append(
                    f"  {site_slug}: real Practice {practice.name!r} names Method "
                    f"{practice.method!r}, which no hosted {site_slug} beamline's "
                    f"device model covers"
                )
    assert not unbacked, (
        "hand-authored non-pending Practice(s) assert a Method no hosted beamline "
        "can derive from its device families. Model the missing hardware, or move "
        "the Practice under `pending:` if it is aspirational:\n" + "\n".join(unbacked)
    )
