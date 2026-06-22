"""Tests for the beamline:* marker expander.

Deployment pages keep hand-authored narrative but inject factual tables from the
beamline descriptor via paired `<!-- beamline:kind -->` markers (the deployment-
tier counterpart of the arch:* markers). This test loads the descriptor and the
expander through the same scripts/ modules the mkdocs on_page_markdown hook uses,
asserting the motion-controller table renders from the descriptor (so it cannot
drift), that the chassis Housing is excluded, that the Drives column inverts the
controller back-reference, that the real controls.md page expands, and that a
malformed marker fails loudly.

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

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_DESCRIPTOR = _REPO_ROOT / "deployments" / "2-bm" / "beamline.yaml"
_EQUIPMENT = _REPO_ROOT / "docs" / "deployments" / "2-bm" / "equipment"
_CONTROLS_PAGE = _EQUIPMENT / "controls.md"
_CONTROLS_SRC_URI = "deployments/2-bm/equipment/controls.md"
_MICROSCOPE_PAGE = _EQUIPMENT / "microscope.md"
_MICROSCOPE_SRC_URI = "deployments/2-bm/equipment/microscope.md"
_ENCLOSURES_PAGE = _REPO_ROOT / "docs" / "deployments" / "2-bm" / "enclosures.md"
_ENCLOSURES_SRC_URI = "deployments/2-bm/enclosures.md"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bd = _load("beamline_descriptor")
bm = _load("beamline_markers")


def _descriptor() -> Any:
    return bd.load(_DESCRIPTOR)


def _motion_controllers() -> list[Any]:
    controls = _descriptor().controls
    assert controls is not None
    return [c for c in controls.motion_controllers if c.family == "MotionController"]


def test_controllers_marker_renders_every_motion_controller_from_descriptor() -> None:
    rendered = bm.render_controllers(_descriptor(), {})
    for controller in _motion_controllers():
        assert f"`{controller.name}`" in rendered


def test_controllers_marker_excludes_the_chassis_housing() -> None:
    rendered = bm.render_controllers(_descriptor(), {})
    assert "RotaryDriveChassis" not in rendered


def test_controllers_marker_drives_column_inverts_the_controller_backref() -> None:
    # AlignmentCamera and DiagnosticFlag both name FrontEndDrive as their
    # controller; the derived Drives column must list them even though the old
    # hand-authored table did not.
    rendered = bm.render_controllers(_descriptor(), {})
    assert "`AlignmentCamera`" in rendered
    assert "`Aperture`" in rendered


def test_controllers_marker_renders_epics_handles_from_descriptor() -> None:
    rendered = bm.render_controllers(_descriptor(), {})
    assert "`2bmHXP:`" in rendered
    assert "`2bmbAERO`" in rendered


def test_controls_page_uses_the_marker_not_a_hand_table() -> None:
    source = _CONTROLS_PAGE.read_text(encoding="utf-8")
    assert "<!-- beamline:controllers -->" in source
    # The motion-controller table must come from the descriptor, so the source
    # must not carry a re-pasted hand table with the same header.
    assert "| Controller | Drives | Model | Protocol | Axes | EPICS handle |" not in source


def test_controls_page_marker_expands_to_the_table() -> None:
    source = _CONTROLS_PAGE.read_text(encoding="utf-8")
    expanded = bm.expand_markers(source, descriptor=_descriptor(), src_uri=_CONTROLS_SRC_URI)
    assert "| Controller | Drives | Model | Protocol | Axes | EPICS handle |" in expanded
    assert "RotaryDriveChassis" not in expanded
    # Each generated table carries the "edit the descriptor, not this table" note.
    assert '!!! info "Generated from the descriptor"' in expanded
    assert "deployments/2-bm/beamline.yaml" in expanded


def test_calibrations_marker_renders_detector_calibrations_from_descriptor() -> None:
    rendered = bm.render_calibrations(_descriptor(), {"stage": "detection"})
    # The objective magnifications (the documented drift home) and the
    # scintillator effective thickness must come from the descriptor.
    assert "`magnification`" in rendered
    assert "9.83" in rendered
    assert "`effective_thickness`" in rendered
    assert "Provisional" in rendered


def test_calibrations_marker_unknown_stage_raises() -> None:
    with pytest.raises(bm.BeamlineMarkerError):
        bm.render_calibrations(_descriptor(), {"stage": "nonsense"})


def test_microscope_page_uses_calibrations_marker_and_expands() -> None:
    source = _MICROSCOPE_PAGE.read_text(encoding="utf-8")
    assert "<!-- beamline:calibrations stage=detection -->" in source
    expanded = bm.expand_markers(source, descriptor=_descriptor(), src_uri=_MICROSCOPE_SRC_URI)
    assert "| Device | Quantity | Value | Operating point | Status | Source |" in expanded
    assert "9.83" in expanded


def test_enclosures_marker_renders_hutches_with_permit_pvs_from_descriptor() -> None:
    rendered = bm.render_enclosures(_descriptor(), {})
    assert "`2-BM-A`" in rendered
    assert "`2-BM-B`" in rendered
    # The permit PVs are the drift-prone bit and must come from the descriptor.
    assert "`S02BM-PSS:StaA:SecureM`" in rendered
    assert "`S02BM-PSS:StaB:SecureM`" in rendered


def test_enclosures_marker_derives_gates_from_group_enclosure() -> None:
    rendered = bm.render_enclosures(_descriptor(), {})
    # front-end names 2-BM-A; detector names 2-BM-B. Both must appear in a Gates
    # cell, derived from each group's enclosure pointer.
    assert "`front-end`" in rendered
    assert "`detector`" in rendered


def test_enclosures_page_uses_marker_and_expands() -> None:
    source = _ENCLOSURES_PAGE.read_text(encoding="utf-8")
    assert "<!-- beamline:enclosures -->" in source
    # The permit PVs must no longer be hand-restated in the prose.
    assert "S02BM-PSS:StaA:SecureM == 1" not in source
    expanded = bm.expand_markers(source, descriptor=_descriptor(), src_uri=_ENCLOSURES_SRC_URI)
    assert "| Enclosure | Role | Anchored to | Gates | Permit signal |" in expanded
    assert "`S02BM-PSS:StaA:SecureM`" in expanded


def test_unknown_marker_kind_raises() -> None:
    markdown = "<!-- beamline:nonsense -->\n<!-- /beamline:nonsense -->"
    with pytest.raises(bm.BeamlineMarkerError):
        bm.expand_markers(markdown, descriptor=_descriptor(), src_uri="deployments/2-bm/x.md")


def test_unpaired_marker_raises() -> None:
    markdown = "<!-- beamline:controllers -->\nno closing marker"
    with pytest.raises(bm.BeamlineMarkerError):
        bm.expand_markers(markdown, descriptor=_descriptor(), src_uri="deployments/2-bm/x.md")
