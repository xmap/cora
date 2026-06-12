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
from typing import TYPE_CHECKING

import pytest

from cora.equipment.aggregates._drawing import DrawingSystem

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_DESCRIPTOR = _REPO_ROOT / "deployments" / "2-bm" / "beamline.yaml"


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


def _humanize(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").strip().capitalize()


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


def test_renders_one_h2_per_group_and_no_em_dash() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    pages = bp.render_all(descriptor)
    assert set(pages) == {"deployments/2-bm/beamline.md"}
    markdown = pages["deployments/2-bm/beamline.md"]

    assert markdown.startswith("# 2-BM beam path")
    for name, _group in descriptor.groups:
        assert f"## {_humanize(name)}" in markdown
    assert "## Controls" in markdown
    assert "## Resources" in markdown
    # a known CORA-modeled device and a promoted marker tag both render
    assert "`Sample_top_X`" in markdown
    assert "`new`" in markdown
    # the P6-50 nested constituents render as their own sub-table
    assert "**P6-50_safety_stack constituents**" in markdown
    # devices link up to the Catalog, and drawings + calibrations render
    assert "../../catalog/families.md" in markdown
    assert "../../catalog/models.md" in markdown
    assert "drawing: EDMS" in markdown
    assert "calibration: magnification" in markdown
    # repo style: no em dashes in generated prose
    assert "—" not in markdown


def test_markers_promoted_from_comments_to_fields() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    devices = {d.name: d for _name, group in descriptor.groups for d in group.devices}
    assert devices["source"].new is True
    assert bool(devices["FE_exit_mask"].confirm) is True
    # a solid CORA-modeled device carries neither marker
    assert devices["Sample_top_X"].new is False
    assert devices["Sample_top_X"].confirm is False


def test_drawing_system_mirror_matches_code() -> None:
    assert {d.value for d in DrawingSystem} == bd.DRAWING_SYSTEMS


def test_drawings_and_calibrations_loaded() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    devices = {d.name: d for _name, group in descriptor.groups for d in group.devices}
    obj0 = devices["MCTOptics_objective_0"]
    assert obj0.drawing is not None
    assert obj0.drawing.system == "EDMS"
    assert obj0.calibrations
    assert obj0.calibrations[0].quantity == "magnification"
    assert devices["Hexapod_2BM"].drawing is not None


def test_malformed_descriptor_raises(tmp_path: Path) -> None:
    missing_beamline = tmp_path / "no_beamline.yaml"
    missing_beamline.write_text("enclosures: []\n", encoding="utf-8")
    with pytest.raises(bd.DescriptorError):
        bd.load(missing_beamline)

    missing_name = tmp_path / "no_name.yaml"
    missing_name.write_text("beamline:\n  facility: aps\n", encoding="utf-8")
    with pytest.raises(bd.DescriptorError):
        bd.load(missing_name)
