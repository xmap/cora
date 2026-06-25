"""Unit tests for the *-bits extraction pass (scripts/reverse_engineer).

Pure-function tests with tiny inline fixtures: no network, no clone. The package
is imported via sys.path + importlib (the dynamic-import bridge used by
apps/api/tests/integration/scenarios/conftest.py), since scripts/ is not on the
type-checker's path.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60)]

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _module(name: str) -> Any:
    return importlib.import_module(name)


parse = _module("reverse_engineer.parse")
mapping = _module("reverse_engineer.mapping")
emit = _module("reverse_engineer.emit")


def _instance(name: str, class_path: str, prefix: str, **kw: Any) -> Any:
    return parse.DeviceInstance(
        name=name,
        class_path=class_path,
        class_name=class_path.split(".")[-1],
        prefix=prefix,
        labels=kw.get("labels", ()),
        kwargs=kw.get("kwargs", {}),
        is_sim=kw.get("is_sim", False),
        is_factory=kw.get("is_factory", False),
    )


def test_parse_devices_yaml_simple_motor_keeps_name_prefix_labels() -> None:
    text = """
ophyd.EpicsMotor:
- {name: m1, prefix: "gp:m1", labels: ["motor", "baseline"]}
"""
    (inst,) = parse.parse_devices_yaml(text)
    assert inst.name == "m1"
    assert inst.class_name == "EpicsMotor"
    assert inst.prefix == "gp:m1"
    assert inst.labels == ("motor", "baseline")
    assert not inst.is_sim and not inst.is_factory


def test_parse_devices_yaml_uppercase_pv_and_kwargs_captured() -> None:
    text = """
id4_common.devices.jj_slits.SlitDevice:
- name: monoslt
  PV: "4idVDCM:"
  motorsDict: {top: m14, bot: m13}
  labels: ["core", "slit"]
"""
    (inst,) = parse.parse_devices_yaml(text)
    assert inst.prefix == "4idVDCM:"
    assert inst.kwargs["motorsDict"] == {"top": "m14", "bot": "m13"}


def test_parse_devices_yaml_flags_sim_and_factory_entries() -> None:
    text = """
apsbits.utils.sim_creator.predefined_device:
- {creator: ophyd.sim.motor, name: sim_motor}
apstools.devices.area_detector_factory.ad_creator:
- {name: eiger, prefix: "8idEiger4m:", labels: ["area_detector", "detectors"]}
"""
    by_name = {i.name: i for i in parse.parse_devices_yaml(text)}
    assert by_name["sim_motor"].is_sim
    assert by_name["eiger"].is_factory


def test_parse_ophyd_module_resolves_literal_motor_axes() -> None:
    src = """
from ophyd import Component as Cpt, Device, EpicsMotor
class Table(Device):
    x = Cpt(EpicsMotor, "m5")
    y = Cpt(EpicsMotor, "m8")
"""
    sketch = parse.parse_ophyd_module(src)["Table"]
    motors = {a.name: a.suffix for a in sketch.axes if a.kind == "motor" and a.resolved}
    assert motors == {"x": "m5", "y": "m8"}
    assert not sketch.is_async


def test_parse_ophyd_module_flags_formatted_and_pseudo() -> None:
    src = """
from ophyd import FormattedComponent as FCpt, Component as Cpt, EpicsMotor, PseudoSingle
from ophyd import PseudoPositioner
class Ana(PseudoPositioner):
    energy = Cpt(PseudoSingle)
    th = FCpt(EpicsMotor, "{prefix}{_th}")
"""
    sketch = parse.parse_ophyd_module(src)["Ana"]
    assert any("FormattedComponent" in r for r in sketch.confirm_reasons)
    assert any("pseudo" in r for r in sketch.confirm_reasons)
    th = next(a for a in sketch.axes if a.name == "th")
    assert not th.resolved


def test_parse_ophyd_module_detects_async_module() -> None:
    src = """
from ophyd_async.core import StandardReadable
class K(StandardReadable):
    pass
"""
    sketch = parse.parse_ophyd_module(src)["K"]
    assert sketch.is_async
    assert any("ophyd_async" in r for r in sketch.confirm_reasons)


def test_infer_enclosure_station_letters_and_sector_only() -> None:
    assert parse.infer_enclosure("8idiSoft:").name == "8-ID-I"
    assert parse.infer_enclosure("4idbSoft:").name == "4-ID-B"
    assert parse.infer_enclosure("2bmb:").name == "2-BM-B"
    sector_only = parse.infer_enclosure("S04ID:")
    assert sector_only.name is None
    assert sector_only.sector == "4-ID"


def test_suggest_family_confident_camera_vs_classname_fallback() -> None:
    camera = _instance(
        "eiger", "apstools.devices.area_detector_factory.ad_creator", "8idEiger4m:", is_factory=True
    )
    family, confirmed = mapping.suggest_family(camera)
    assert family == "Camera" and confirmed
    unknown = _instance("x", "pkg.Foo", "p:")
    family2, confirmed2 = mapping.suggest_family(unknown)
    assert family2 == "Foo" and not confirmed2


def test_to_candidate_device_builds_pv_from_kwargs_and_enclosure() -> None:
    inst = _instance(
        "rl1",
        "id8_common.devices.transfocator.Transfocator",
        "8iddSoft:TRANS:",
        kwargs={"pv_x": "m2", "pv_y": "m1"},
        labels=("slit",),
    )
    candidate = mapping.to_candidate_device(inst, None)
    assert candidate.pv == {"x": "8iddSoft:TRANS:m2", "y": "8iddSoft:TRANS:m1"}
    assert candidate.enclosure == "8-ID-D"
    assert candidate.confirm_reasons


def test_to_candidate_device_detector_bucketed_to_detection() -> None:
    inst = _instance(
        "eiger",
        "apstools.devices.area_detector_factory.ad_creator",
        "8idEiger4m:",
        labels=("area_detector", "detectors"),
        is_factory=True,
    )
    candidate = mapping.to_candidate_device(inst, None)
    assert candidate.stage == "detection"
    assert candidate.family == "Camera"


def test_candidate_yaml_self_validates_against_loader(tmp_path: Path) -> None:
    inst = _instance("m1", "ophyd.EpicsMotor", "2bmb:m1", labels=("motor",))
    candidate = mapping.to_candidate_device(inst, None)
    text = emit.render_candidate_yaml("2-BM", "aps", [candidate])
    path = tmp_path / "beamline.candidate.yaml"
    path.write_text(text, encoding="utf-8")
    ok, message = emit.self_validate(path)
    assert ok, message


def test_recurrence_marks_graduated_and_candidates() -> None:
    slit_a = mapping.to_candidate_device(
        _instance("s1", "p.Slit", "8idaSoft:", labels=("slit",)), None
    )
    slit_b = mapping.to_candidate_device(
        _instance("s2", "p.Slit", "4idbSoft:", labels=("slit",)), None
    )
    rendered = emit.render_recurrence_md(
        {"8id-bits": [slit_a], "polar-bits": [slit_b]}, graduated={"Slit"}
    )
    assert "Slit" in rendered and "graduated" in rendered

    foo_a = mapping.to_candidate_device(_instance("u1", "p.Foo", "8idaSoft:"), None)
    foo_b = mapping.to_candidate_device(_instance("u2", "p.Foo", "4idbSoft:"), None)
    rendered2 = emit.render_recurrence_md({"r1": [foo_a], "r2": [foo_b]}, graduated=set())
    assert "GRADUATION CANDIDATE" in rendered2
