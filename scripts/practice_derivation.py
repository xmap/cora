"""Derive a beamline's practiceable Methods from its device-Family coverage.

Realizes Lock 2 of the operations-layer re-derivation
([[project-operations-layer-rederivation-design]]): a Practice is a Method a
beamline can actually run, and a beamline can run a Method when its installed
devices cover the Method's hardware contract. Rather than hand-author one
`(Method, site)` Practice per beamline (which concentrated all real operations
data at the one pilot that got the hand-authoring, APS), derive the roster:

    practiceable(beamline) = { method : method.needed_families subset of
                               union(device.family for device in beamline) }

This is the SAME set-cover the spine already computes at bind time
(`recipe/features/define_plan/decider.py`: a Plan's bound Assets' families must
cover the Method's `needed_family_ids`), lifted to the descriptor layer so the
bridge contract runs across the whole fleet from data, not from curation.

Coverage is NECESSARY, not sufficient: a beamline whose families cover a
Method CAN host it hardware-wise; whether the beamline's science actually uses
it is a separate (operator / technique) fact. So the derived roster is the set
of hardware-feasible Methods, and a thin roster (or an empty one) is an honest
signal that the catalog carries no Method for that beamline's technique yet
(the tomography-bias the memo diagnoses), not a bug in this module.

Zero cora.* imports by design (mirrors catalog_descriptor / beamline_descriptor):
the docs build runs under a lean interpreter without the cora package. The
descriptor loaders this module composes carry the same constraint.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import beamline_descriptor
import catalog_descriptor


def beamline_families(descriptor: beamline_descriptor.BeamlineDescriptor) -> frozenset[str]:
    """Every distinct Family present on a beamline, across all sources.

    Walks the beam-path groups, the cross-cutting controls section (motion
    controllers + triggering), and each device's nested constituents, so a
    Family declared only on a sub-component (e.g. an Objective inside a
    Microscope housing) still counts toward coverage. Devices with no `family`
    (unmodelled or passive-only) contribute nothing and are skipped.
    """
    families: set[str] = set()

    def _walk(devices: list[beamline_descriptor.Device]) -> None:
        for device in devices:
            if device.family:
                families.add(device.family)
            if device.constituents:
                _walk(device.constituents)

    for _stage, group in descriptor.groups:
        _walk(group.devices)

    controls = descriptor.controls
    if controls is not None:
        _walk(controls.motion_controllers)
        _walk(controls.triggering)

    return frozenset(families)


@dataclass(frozen=True)
class DerivedRoster:
    """A beamline's hardware-feasible Methods, plus the coverage inputs.

    `practiceable` is the derived Method-name set. `families` and the
    per-method `missing_families` are kept so a renderer or a guard can explain
    WHY a Method is in or out without recomputing the set-cover.
    """

    families: frozenset[str]
    practiceable: frozenset[str]
    missing_families: dict[str, frozenset[str]]


def _roles_presented_by(
    families: frozenset[str],
    catalog: catalog_descriptor.Catalog,
) -> frozenset[str]:
    """The set of Role names some family in `families` presents (catalog
    `presents_as`). Lets a Method's `required_roles` be covered anatomically:
    a beamline covers a Role when it has a family that presents it."""
    presented: set[str] = set()
    for fam in catalog.families:
        if fam.name in families:
            presented.update(fam.presents_as)
    return frozenset(presented)


def derive_roster(
    descriptor: beamline_descriptor.BeamlineDescriptor,
    catalog: catalog_descriptor.Catalog,
) -> DerivedRoster:
    """Compute the practiceable-Method roster for one beamline.

    A Method is practiceable when the beamline covers BOTH its hardware
    contracts: every `needed_families` entry is a beamline family (the
    anatomical escape hatch), AND every `required_roles` entry is presented by
    some beamline family (the federation-portable role binding, via catalog
    `presents_as`). Coverage of the two fields is ANDed.

    A Method declaring NEITHER field is excluded: it has no hardware contract,
    so coverage is vacuous and it would appear on every roster as noise. Such
    Methods are site-ceremony, not hardware-gated Practices, out of scope here.
    """
    families = beamline_families(descriptor)
    presented_roles = _roles_presented_by(families, catalog)
    practiceable: set[str] = set()
    missing: dict[str, frozenset[str]] = {}
    for method in catalog.methods:
        needed = frozenset(method.needed_families)
        required_roles = frozenset(method.required_roles)
        if not needed and not required_roles:
            continue
        gap = (needed - families) | frozenset(
            f"role:{r}" for r in (required_roles - presented_roles)
        )
        if gap:
            missing[method.name] = gap
        else:
            practiceable.add(method.name)
    return DerivedRoster(
        families=families,
        practiceable=frozenset(practiceable),
        missing_families=missing,
    )


def derive_all(
    deployments_dir: str | Path,
    catalog_path: str | Path,
) -> dict[str, DerivedRoster]:
    """Derive rosters for every deployment carrying a beamline.yaml.

    Keyed by deployment slug (the directory name), sorted for deterministic
    iteration. Discovers deployments the same way the mkdocs hook does, so a
    new beamline is covered automatically.
    """
    deployments_dir = Path(deployments_dir)
    catalog = catalog_descriptor.load(catalog_path)
    rosters: dict[str, DerivedRoster] = {}
    for beamline_yaml in sorted(deployments_dir.glob("*/beamline.yaml")):
        slug = beamline_yaml.parent.name
        descriptor = beamline_descriptor.load(beamline_yaml)
        rosters[slug] = derive_roster(descriptor, catalog)
    return rosters
