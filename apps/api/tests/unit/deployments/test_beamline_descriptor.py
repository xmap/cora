"""Round-trip test for the beamline descriptor schema and renderer.

The descriptor at deployments/2-bm/beamline.yaml is the single source the docs
build renders from. This test loads it through the same scripts/ modules the
mkdocs on_files hook uses, asserting it validates and renders, that the
new/confirm markers survived as real fields, and that a malformed descriptor
fails loudly. It is a pure parser test (no I/O beyond reading the file), hence
the unit tier.

The scripts/ modules are loaded via importlib (the dynamic-import bridge used by
tests/integration/scenarios/conftest.py), since scripts/ is not on the
type-checker's path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from cora.equipment.aggregates._drawing import DrawingSystem

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_DESCRIPTOR = _REPO_ROOT / "deployments" / "2-bm" / "beamline.yaml"
_CATALOG = _REPO_ROOT / "catalog" / "catalog.yaml"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bd = _load("beamline_descriptor")
bp = _load("beamline_pages")
cd = _load("catalog_descriptor")


def _render_with_catalog() -> str:
    descriptor = bd.load(_DESCRIPTOR)
    catalog = cd.load(_CATALOG)
    pages = bp.render_all(
        descriptor,
        catalog_families=frozenset(f.name for f in catalog.families),
        catalog_models=frozenset(m.name for m in catalog.models),
    )
    return pages["deployments/2-bm/beamline.md"]


def _humanize(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").strip().capitalize()


def _walk_devices(descriptor: Any) -> list[Any]:
    # Every modelled device in the descriptor: the beam-walk groups plus the
    # cross-cutting controls section (motion controllers, triggering), recursing
    # into nested constituents (the P6-50 SafetyStack, the Microscope chain) so a
    # drift on a controls device or a nested constituent cannot hide from the
    # catalog cross-checks below.
    found: list[Any] = []

    def visit(device: Any) -> None:
        found.append(device)
        constituents: list[Any] = device.constituents or []
        for constituent in constituents:
            visit(constituent)

    for _name, group in descriptor.groups:
        for device in group.devices:
            visit(device)
    controls = descriptor.controls
    if controls is not None:
        for device in (*controls.motion_controllers, *controls.triggering):
            visit(device)
    return found


def test_descriptor_loads_and_validates() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    assert descriptor.beamline.name == "2-BM"
    assert descriptor.beamline.facility == "aps"
    assert descriptor.groups, "expected at least one beam-path group"
    group_names = [name for name, _ in descriptor.groups]
    for expected in (
        "front-end",
        "conditioning-optics",
        "beam-defining-and-safety",
        "sample-environment",
        "detector",
    ):
        assert expected in group_names
    assert descriptor.controls is not None
    assert descriptor.resources is not None


def test_enclosures_carry_facility_code_and_permit_pv() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    enclosures = {e.name: e for e in descriptor.enclosures}
    assert {"2-BM-A", "2-BM-B"} <= set(enclosures)
    for name in ("2-BM-A", "2-BM-B"):
        assert enclosures[name].facility_code == "aps"
    # the per-hutch search-and-secure permit PVs are confirmed post-migration (PSS-1)
    assert enclosures["2-BM-A"].permit_signal == "S02BM-PSS:StaA:SecureM"
    assert enclosures["2-BM-B"].permit_signal == "S02BM-PSS:StaB:SecureM"


def test_unknown_enclosure_ref_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad_enclosure_ref.yaml"
    bad.write_text(
        "beamline:\n  name: T\n"
        "enclosures:\n  - name: hutch-a\n    facility_code: aps\n"
        "front-end:\n  enclosure: not-declared\n  devices: []\n",
        encoding="utf-8",
    )
    with pytest.raises(bd.DescriptorError):
        bd.load(bad)


def test_renders_enclosures_table_facility_and_permit_columns() -> None:
    markdown = _render_with_catalog()
    assert "## Enclosures" in markdown
    assert "| Enclosure | Role | Facility | Permit signal |" in markdown
    # each hutch row carries its containing-Facility slug and its permit PV
    assert "`2-BM-A`" in markdown
    assert "`2-BM-B`" in markdown
    assert "`aps`" in markdown
    assert "`S02BM-PSS:StaA:SecureM`" in markdown
    assert "`S02BM-PSS:StaB:SecureM`" in markdown


def test_renders_one_h2_per_group_and_no_em_dash() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    markdown = _render_with_catalog()

    assert markdown.startswith("# 2-BM layout")
    for name, _group in descriptor.groups:
        assert f"## {_humanize(name)}" in markdown
    assert "## Controls" in markdown
    assert "## Resources" in markdown
    # a known CORA-modeled device and a promoted marker tag both render
    assert "`SampleTop_X`" in markdown
    assert "`new`" in markdown
    # the P6-50 nested constituents render as their own sub-table
    assert "**SafetyStack constituents**" in markdown
    # a family present in the Catalog links up; a pending one renders plain (no fake link)
    assert "[`RotaryStage`](../../catalog/families.md)" in markdown
    assert "`Mask`" in markdown
    assert "[`Mask`](../../catalog/families.md)" not in markdown
    # drawings + calibrations (with status) + the confirm note all render
    assert "drawing: EDMS" in markdown
    assert "calibration: magnification = 9.83 (Provisional" in markdown
    assert "confirm: count and thickness" in markdown
    # repo style: no em dashes in generated prose (chr() keeps the literal out of source)
    assert chr(0x2014) not in markdown


def test_markers_promoted_from_comments_to_fields() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    devices = {d.name: d for _name, group in descriptor.groups for d in group.devices}
    assert devices["source"].new is True
    assert bool(devices["Mask"].confirm) is True
    # a solid CORA-modeled device carries neither marker
    assert devices["SampleTop_X"].new is False
    assert devices["SampleTop_X"].confirm is False


def test_drawing_system_mirror_matches_code() -> None:
    assert {d.value for d in DrawingSystem} == bd.DRAWING_SYSTEMS


def test_drawings_and_calibrations_loaded() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    devices = {d.name: d for _name, group in descriptor.groups for d in group.devices}
    obj0 = devices["Objective_10x"]
    assert obj0.drawing is not None
    assert obj0.drawing.system == "EDMS"
    assert obj0.calibrations
    assert obj0.calibrations[0].quantity == "magnification"
    assert devices["Hexapod"].drawing is not None


def test_device_model_references_resolve_in_catalog() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    catalog = cd.load(_CATALOG)
    model_names = {m.name for m in catalog.models}
    devices = _walk_devices(descriptor)
    # guard against a vacuous pass if the walk ever regresses to empty
    assert sum(1 for d in devices if d.model) >= 5
    dangling = sorted(
        f"{d.name} -> {d.model}" for d in devices if d.model and d.model not in model_names
    )
    assert not dangling, f"beamline devices bind catalog models that do not exist: {dangling}"


def test_device_family_is_declared_by_its_bound_model() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    catalog = cd.load(_CATALOG)
    declared = {m.name: set(m.declared_families) for m in catalog.models}
    devices = _walk_devices(descriptor)
    # guard against a vacuous pass if the walk ever regresses to empty
    assert sum(1 for d in devices if d.model and d.family) >= 5
    mismatched = sorted(
        f"{d.name}: family {d.family} not in {sorted(declared[d.model])} (model {d.model})"
        for d in devices
        if d.model and d.family and d.model in declared and d.family not in declared[d.model]
    )
    assert not mismatched, (
        f"device family disagrees with its bound model's declared_families: {mismatched}"
    )


def test_malformed_descriptor_raises(tmp_path: Path) -> None:
    missing_beamline = tmp_path / "no_beamline.yaml"
    missing_beamline.write_text("enclosures: []\n", encoding="utf-8")
    with pytest.raises(bd.DescriptorError):
        bd.load(missing_beamline)

    missing_name = tmp_path / "no_name.yaml"
    missing_name.write_text("beamline:\n  facility: aps\n", encoding="utf-8")
    with pytest.raises(bd.DescriptorError):
        bd.load(missing_name)
