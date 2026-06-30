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
cli = _module("reverse_engineer.cli")


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


# DESY OnlineXML (PETRA III, Tango) extraction path.

_ONLINE_XML_TWO_DEVICES = """<?xml version="1.0"?>
<hw>
<device>
   <name>eh1_mot01</name>
   <type>stepping_motor</type>
   <module>oms58</module>
   <device>p01/motor/eh1.01</device>
   <hostname>haspp01eh1:10000</hostname>
   <control>tango</control>
</device>
<device>
   <name>eh1_t01</name>
   <type>counter</type>
   <module>sis3820</module>
   <device>p01/counter/eh1.01</device>
   <hostname>haspp01eh1:10000</hostname>
   <control>tango</control>
</device>
</hw>
"""


def test_parse_online_xml_extracts_device_fields() -> None:
    devices = {d.name: d for d in parse.parse_online_xml(_ONLINE_XML_TWO_DEVICES)}
    motor = devices["eh1_mot01"]
    assert motor.type == "stepping_motor"
    assert motor.module == "oms58"
    assert motor.address == "p01/motor/eh1.01"
    assert motor.host == "haspp01eh1:10000"
    assert motor.control == "tango"


def test_parse_online_xml_tolerates_missing_children() -> None:
    text = """<?xml version="1.0"?>
<hw>
<device>
   <name>bare</name>
   <type>motor</type>
   <device>None</device>
</device>
</hw>
"""
    (device,) = parse.parse_online_xml(text)
    assert device.name == "bare"
    assert device.type == "motor"
    assert device.module is None
    assert device.address is None
    assert device.host is None


def test_infer_enclosure_tango_endstation_and_sector_only() -> None:
    assert parse.infer_enclosure_tango("haspp01eh1:10000").name == "P01-EH1"
    assert parse.infer_enclosure_tango("hasep21eh3:10000").name == "P21-EH3"
    sector_only = parse.infer_enclosure_tango("hasnp64:10000")
    assert sector_only.name == "P64"
    assert sector_only.station is None


def test_suggest_family_tango_confident_vs_module_fallback() -> None:
    pilatus = parse.TangoDevice("det", "detector", "pilatus300k", "p03/det/1", "h:10000", "tango")
    family, confirmed = mapping.suggest_family_tango(pilatus)
    assert family == "Camera" and confirmed
    mono = parse.TangoDevice("mono", "motor", "lom", "p09/mono/1", "h:10000", "tango")
    assert mapping.suggest_family_tango(mono) == ("Monochromator", True)
    oms = parse.TangoDevice("m1", "stepping_motor", "oms58", "p01/motor/1", "h:10000", "tango")
    family2, confirmed2 = mapping.suggest_family_tango(oms)
    assert family2 == "oms58" and not confirmed2


def test_to_candidate_device_tango_motor_and_filtered_counter() -> None:
    devices = {d.name: d for d in parse.parse_online_xml(_ONLINE_XML_TWO_DEVICES)}
    motor = mapping.to_candidate_device_tango(devices["eh1_mot01"])
    assert motor is not None
    assert motor.pv == "p01/motor/eh1.01"
    assert motor.enclosure == "P01-EH1"
    assert motor.confirm_reasons
    assert mapping.to_candidate_device_tango(devices["eh1_t01"]) is None


def test_to_candidate_device_tango_detector_bucketed_to_detection() -> None:
    det = parse.TangoDevice(
        "lambda1", "detector", "lambda", "p03/det/lambda", "haspp03:10000", "tango"
    )
    candidate = mapping.to_candidate_device_tango(det)
    assert candidate is not None
    assert candidate.stage == "detection"
    assert candidate.family == "Camera"


def test_tango_candidate_yaml_self_validates_against_loader(tmp_path: Path) -> None:
    device = parse.TangoDevice(
        "eh1_mot01", "stepping_motor", "oms58", "p01/motor/eh1.01", "haspp01eh1:10000", "tango"
    )
    candidate = mapping.to_candidate_device_tango(device)
    assert candidate is not None
    text = emit.render_candidate_yaml("P01", "petra-iii", [candidate])
    path = tmp_path / "beamline.candidate.yaml"
    path.write_text(text, encoding="utf-8")
    ok, message = emit.self_validate(path)
    assert ok, message


# Output-directory naming: the dir is the beamline ID, never the repo stem.


def test_slugify_lowercases_beamline_id_to_directory_slug() -> None:
    assert cli._slugify("4-ID") == "4-id"
    assert cli._slugify("12-ID-E") == "12-id-e"
    assert cli._slugify("2-BM") == "2-bm"


def test_slugify_collapses_non_alphanumeric_runs() -> None:
    assert cli._slugify("6-ID-B") == "6-id-b"
    assert cli._slugify("P01 EH1") == "p01-eh1"
    assert cli._slugify("--4-ID--") == "4-id"


def _candidate(enclosure: str | None) -> Any:
    return mapping.CandidateDevice(
        name="m1",
        family="EpicsMotor",
        family_confirmed=False,
        pv="4idbSoft:m1",
        labels=(),
        role_hints=(),
        enclosure=enclosure,
        stage="source",
        source_class="ophyd.EpicsMotor",
        confirm_reasons=(),
        is_sim=False,
    )


def test_beamline_name_prefers_enclosure_sector_over_repo_stem() -> None:
    devices = [_candidate("4-ID-B"), _candidate("4-ID-B"), _candidate("4-ID-G")]
    assert cli._beamline_name(devices, "polar-bits") == "4-ID"


def test_beamline_name_falls_back_to_repo_stem_without_station_enclosure() -> None:
    assert cli._beamline_name([_candidate(None)], "usaxs-bits") == "usaxs-bits"


# MXCuBE HardwareObjects (EMBL Hamburg, ALBA, SOLEIL) extraction path.

_MXCUBE_DETECTOR = """<object class="EMBLDetector">
  <channel type="tine" name="chanStatus" tinename="/P13/detector/eiger16m">status</channel>
  <type>Eiger</type>
  <model>16M</model>
</object>
"""

_MXCUBE_MOTOR = """<object class="ExporterMotor">
  <exporter_address>p14md302.embl-hamburg.de:9001</exporter_address>
  <actuator_name>Omega</actuator_name>
</object>
"""

_MXCUBE_SOFTWARE = """<object class="ISPyBClient">
  <ldap_server>ldap.embl-hamburg.de</ldap_server>
</object>
"""


def test_parse_mxcube_object_reads_class_handle_model() -> None:
    det = parse.parse_mxcube_object(_MXCUBE_DETECTOR, "eh1/detector-eiger16m")
    assert det is not None
    assert det.obj_class == "EMBLDetector"
    assert det.name == "detector-eiger16m"
    assert det.rel_path == "eh1/detector-eiger16m"
    assert det.handle == "/P13/detector/eiger16m"
    assert det.model == "16M"
    assert not det.is_mockup
    motor = parse.parse_mxcube_object(_MXCUBE_MOTOR, "eh1/diff-omega")
    assert motor is not None
    assert motor.handle == "p14md302.embl-hamburg.de:9001"


def test_parse_mxcube_object_rejects_non_object_and_malformed() -> None:
    assert parse.parse_mxcube_object("<procedure/>", "x") is None
    assert parse.parse_mxcube_object("<object>no class</object>", "x") is None
    assert parse.parse_mxcube_object("<object class=", "x") is None


def test_infer_enclosure_mxcube_endstation_and_root() -> None:
    assert parse.infer_enclosure_mxcube("eh1/detector-eiger16m", "P14").name == "P14-EH1"
    assert parse.infer_enclosure_mxcube("eh2/diff-omega", "PE2").name == "PE2-EH2"
    root = parse.infer_enclosure_mxcube("diffractometer", "P14")
    assert root.name == "P14"
    assert root.station is None


def test_suggest_family_mxcube_confident_vs_class_fallback() -> None:
    diff = parse.MxcubeDevice(
        "diffractometer", "EMBLMiniDiff", "diffractometer", "h:9001", None, None, False
    )
    assert mapping.suggest_family_mxcube(diff) == ("Goniometer", True)
    det = parse.MxcubeDevice("d", "EMBLDetector", "eh1/d", "/P13/det", "Eiger", "16M", False)
    assert mapping.suggest_family_mxcube(det) == ("Camera", True)
    motor = parse.MxcubeDevice(
        "diff-omega", "ExporterMotor", "eh1/diff-omega", "h:9001", None, None, False
    )
    family, confirmed = mapping.suggest_family_mxcube(motor)
    assert family == "ExporterMotor" and not confirmed


def test_to_candidate_device_mxcube_device_vs_filtered_software_and_mockup() -> None:
    det = parse.parse_mxcube_object(_MXCUBE_DETECTOR, "eh1/detector-eiger16m")
    assert det is not None
    cand = mapping.to_candidate_device_mxcube(det, "P13")
    assert cand is not None
    assert cand.family == "Camera"
    assert cand.stage == "detection"
    assert cand.enclosure == "P13-EH1"
    assert cand.pv == "/P13/detector/eiger16m"
    software = parse.parse_mxcube_object(_MXCUBE_SOFTWARE, "data-collection")
    assert software is not None
    assert mapping.to_candidate_device_mxcube(software, "P13") is None
    mockup = parse.MxcubeDevice("m", "MotorMockup", "m", None, None, None, True)
    assert mapping.to_candidate_device_mxcube(mockup, "P13") is None


def test_mxcube_candidate_yaml_self_validates_against_loader(tmp_path: Path) -> None:
    diff = parse.MxcubeDevice(
        "diffractometer", "EMBLMiniDiff", "diffractometer", "p14md302:9001", None, None, False
    )
    candidate = mapping.to_candidate_device_mxcube(diff, "P14")
    assert candidate is not None
    text = emit.render_candidate_yaml("P14", "petra-iii", [candidate])
    path = tmp_path / "beamline.candidate.yaml"
    path.write_text(text, encoding="utf-8")
    ok, message = emit.self_validate(path)
    assert ok, message


def test_mxcube_beamline_label_derivation() -> None:
    assert cli._mxcube_beamline_label("mxcubecore/configuration/embl_hh_p14", None) == "P14"
    assert cli._mxcube_beamline_label("configuration/desy_p11", None) == "P11"
    assert cli._mxcube_beamline_label("configuration/embl_hh_p13", "P13") == "P13"
