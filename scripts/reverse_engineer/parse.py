"""Parse beamline controls sources into candidate-device inputs.

Pure functions over text; no network, no cora.* imports. Anything that cannot be
resolved statically is recorded as a confirm reason rather than guessed, so the
emitter can flag it. ophyd_async modules are detected and skipped (their device
trees are not class-attribute Cpt trees, so the static oracle does not apply).

Three source families are parsed here:

  - EPICS *-bits: Guarneri devices.yml + ophyd device classes + PV grammar (APS).
  - DESY OnlineXML: the online_*.xml per-endstation device registry of a PETRA III
    beamline (Tango device name/class/address/host).
  - MXCuBE HardwareObjects: the per-beamline configuration/<beamline>/*.xml device
    objects of an MXCuBE deployment (EMBL Hamburg, ALBA, SOLEIL), each file an
    <object class="..."> with an Exporter / TINE control handle.

All converge on the control-system-agnostic mapping.CandidateDevice downstream.
"""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import yaml

# Call names used to declare ophyd components, including the conventional aliases
# (`from ophyd import Component as Cpt`, `FormattedComponent as FCpt`).
_PLAIN_COMPONENT_CALLS: frozenset[str] = frozenset({"Cpt", "Component"})
_FORMATTED_COMPONENT_CALLS: frozenset[str] = frozenset({"FCpt", "FormattedComponent"})
_COMPONENT_CALLS: frozenset[str] = _PLAIN_COMPONENT_CALLS | _FORMATTED_COMPONENT_CALLS

# Device-class names whose leaves are physical motion axes.
_MOTOR_CLASSES: frozenset[str] = frozenset({"EpicsMotor"})
# Device-class names that are computed or configuration, not physical axes.
_PSEUDO_CLASSES: frozenset[str] = frozenset({"PseudoSingle"})
_SIGNAL_CLASSES: frozenset[str] = frozenset(
    {"Signal", "EpicsSignal", "EpicsSignalRO", "EpicsSignalWithRBV"}
)

# Sim and factory markers in a device class path.
_SIM_MARKERS: tuple[str, ...] = ("ophyd.sim.", ".sim_creator.", "predefined_device")
_FACTORY_MARKERS: tuple[str, ...] = ("ad_creator", "_creator", "_factory")


class _LenientLoader(yaml.SafeLoader):
    """SafeLoader that tolerates the Python-specific tags some devices.yml carry.

    A few *-bits repos store ophyd class references as !!python/name: tags, which
    safe_load rejects. Here they degrade to the dotted name (or the plain value)
    so the rest of the file still parses.
    """


def _construct_python_name(loader: Any, tag_suffix: str, node: Any) -> str:
    return tag_suffix


def _construct_unknown(loader: Any, tag_suffix: str, node: Any) -> Any:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)


_LenientLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/name:", _construct_python_name
)
_LenientLoader.add_multi_constructor("", _construct_unknown)


def _lenient_load(text: str) -> Any:
    return yaml.load(text, Loader=_LenientLoader)


@dataclass(frozen=True)
class DeviceInstance:
    """One entry in a Guarneri devices.yml: a named device of a class with a prefix."""

    name: str
    class_path: str
    class_name: str
    prefix: str | None
    labels: tuple[str, ...]
    kwargs: dict[str, Any]
    is_sim: bool
    is_factory: bool


@dataclass(frozen=True)
class Axis:
    """A component leaf on an ophyd device class."""

    name: str
    suffix: str
    kind: str  # "motor" | "pseudo" | "signal" | "nested" | "other"
    resolved: bool  # False when the suffix is a FormattedComponent / not a literal


@dataclass(frozen=True)
class OphydSketch:
    """The statically extractable shape of one ophyd Device subclass."""

    class_name: str
    bases: tuple[str, ...]
    axes: tuple[Axis, ...]
    confirm_reasons: tuple[str, ...]
    is_async: bool


@dataclass(frozen=True)
class EnclosureHint:
    """A candidate enclosure inferred from a PV prefix or a station label."""

    name: str | None
    sector: str | None
    station: str | None
    confirm: bool = True


def _classify_device_class(class_name: str) -> str:
    if class_name in _MOTOR_CLASSES:
        return "motor"
    if class_name in _PSEUDO_CLASSES:
        return "pseudo"
    if class_name in _SIGNAL_CLASSES:
        return "signal"
    return "nested"


def parse_devices_yaml(text: str) -> list[DeviceInstance]:
    """Parse a Guarneri devices.yml: a mapping of class path to a list of entries.

    Each entry is `{name, prefix|PV, labels, **kwargs}`. Sim creators and factory
    entries (ad_creator) are kept but flagged so the emitter can handle them.
    """
    try:
        raw = _lenient_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(raw, dict):
        return []

    instances: list[DeviceInstance] = []
    for class_path, entries in raw.items():
        if not isinstance(class_path, str) or not isinstance(entries, list):
            continue
        class_name = class_path.split(".")[-1]
        is_sim = any(marker in class_path for marker in _SIM_MARKERS)
        is_factory = any(marker in class_path for marker in _FACTORY_MARKERS)
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str):
                continue
            prefix = entry.get("prefix") or entry.get("PV")
            labels_raw = entry.get("labels") or []
            labels = tuple(str(label) for label in labels_raw if isinstance(label, str))
            kwargs = {
                key: value
                for key, value in entry.items()
                if key not in {"name", "prefix", "PV", "labels"}
            }
            instances.append(
                DeviceInstance(
                    name=name,
                    class_path=class_path,
                    class_name=class_name,
                    prefix=prefix if isinstance(prefix, str) else None,
                    labels=labels,
                    kwargs=kwargs,
                    is_sim=is_sim,
                    is_factory=is_factory,
                )
            )
    return instances


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _first_class_arg(call: ast.Call) -> str | None:
    if not call.args:
        return None
    return _call_name(call.args[0])


def _literal_suffix(call: ast.Call) -> str | None:
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        value = call.args[1].value
        if isinstance(value, str):
            return value
    return None


def parse_ophyd_module(source: str) -> dict[str, OphydSketch]:
    """AST-walk a devices/*.py module into a map of class name to OphydSketch.

    Resolves plain Component(EpicsMotor, "suffix") leaves to motor axes. Marks
    FormattedComponent leaves, pseudo axes, and unknown bases with confirm reasons
    rather than guessing. If the module imports ophyd_async, every class in it is
    marked is_async (the Cpt oracle does not apply) and left for a human.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    module_async = _imports_ophyd_async(tree)

    sketches: dict[str, OphydSketch] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = tuple(
            name for name in (_call_name(base) for base in node.bases) if name
        )
        axes, reasons = _class_axes(node)
        if module_async:
            reasons = (
                *reasons,
                "ophyd_async module: device tree not statically parseable",
            )
        sketches[node.name] = OphydSketch(
            class_name=node.name,
            bases=bases,
            axes=axes,
            confirm_reasons=tuple(dict.fromkeys(reasons)),
            is_async=module_async,
        )
    return sketches


def _imports_ophyd_async(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "ophyd_async"
        ):
            return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("ophyd_async"):
                    return True
    return False


def _class_axes(node: ast.ClassDef) -> tuple[tuple[Axis, ...], tuple[str, ...]]:
    axes: list[Axis] = []
    reasons: list[str] = []
    for stmt in node.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name) or not isinstance(stmt.value, ast.Call):
            continue
        call = stmt.value
        call_name = _call_name(call.func)
        if call_name not in _COMPONENT_CALLS:
            continue
        device_class = _first_class_arg(call) or "?"
        kind = _classify_device_class(device_class)
        if kind == "pseudo":
            reasons.append(f"{target.id}: pseudo axis (computed, not a physical motor)")
        if call_name in _FORMATTED_COMPONENT_CALLS:
            axes.append(Axis(name=target.id, suffix="", kind=kind, resolved=False))
            reasons.append(
                f"{target.id}: FormattedComponent suffix resolved at runtime"
            )
            continue
        suffix = _literal_suffix(call)
        if suffix is None:
            axes.append(Axis(name=target.id, suffix="", kind=kind, resolved=False))
            reasons.append(f"{target.id}: non-literal or absent component suffix")
            continue
        axes.append(Axis(name=target.id, suffix=suffix, kind=kind, resolved=True))
    return tuple(axes), tuple(reasons)


# Prefix grammars seen across the corpus. Station letter, where present, is a
# candidate enclosure branch; the mapping always carries confirm=True.
_PREFIX_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"^(?P<sector>\d+)bm(?P<station>[a-z])", "bm"),
    (r"^(?P<sector>\d+)id(?P<station>[a-z])", "id"),
    (r"^S0*(?P<sector>\d+)ID", "id"),
)


def infer_enclosure(prefix: str | None) -> EnclosureHint:
    """Infer a candidate enclosure from a PV prefix or a station label.

    Examples: 2bmb: -> 2-BM-B, 8idiSoft: -> 8-ID-I, 4idbSoft: -> 4-ID-B,
    S04ID: -> 4-ID (no station). Always confirm=True; the station-to-enclosure
    mapping is a guess.
    """
    if not prefix:
        return EnclosureHint(name=None, sector=None, station=None)
    for pattern, branch in _PREFIX_PATTERNS:
        match = re.match(pattern, prefix)
        if not match:
            continue
        sector = match.group("sector")
        station = match.groupdict().get("station")
        branch_label = "BM" if branch == "bm" else "ID"
        if station:
            name = f"{sector}-{branch_label}-{station.upper()}"
            return EnclosureHint(
                name=name, sector=f"{sector}-{branch_label}", station=station
            )
        return EnclosureHint(name=None, sector=f"{sector}-{branch_label}", station=None)
    return EnclosureHint(name=None, sector=None, station=None)


@dataclass(frozen=True)
class TangoDevice:
    """One <device> block in a DESY OnlineXML (online_*.xml) registry.

    Mirrors the registry shape: a logical name, a role type (stepping_motor,
    counter, mca, detector, ...), the Tango device class (module), the Tango
    device address (domain/family/member), the Tango DB host, and the control
    protocol. Any child absent in the XML is None.
    """

    name: str
    type: str | None
    module: str | None
    address: str | None
    host: str | None
    control: str | None


def _child_text(device: ET.Element, tag: str) -> str | None:
    """Return the stripped text of a direct child tag, or None if absent or empty.

    The address lives in the <device> child element (a registry quirk: the row is
    <device> and it nests its own <device> holding the Tango address). Callers ask
    for that nested tag by name like any other child.
    """
    child = device.find(tag)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    if not text or text == "None":
        return None
    return text


def parse_online_xml(text: str) -> list[TangoDevice]:
    """Parse a DESY OnlineXML registry into TangoDevice rows.

    The file is a flat <hw><device>...</device>...</hw> tree. Each row's Tango
    address is the nested <device> element's text (the registry reuses the tag).
    Malformed XML yields an empty list rather than raising, mirroring the lenient
    contract of parse_devices_yaml.
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    devices: list[TangoDevice] = []
    for element in root.findall("device"):
        name = _child_text(element, "name")
        if name is None:
            continue
        devices.append(
            TangoDevice(
                name=name,
                type=_child_text(element, "type"),
                module=_child_text(element, "module"),
                address=_child_text(element, "device"),
                host=_child_text(element, "hostname"),
                control=_child_text(element, "control"),
            )
        )
    return devices


# DESY Tango DB host grammar: an optional has[pen] facility prefix, the p<NN>
# beamline, then an optional endstation token (eh1, ch2, dif, mag, lab, ...).
# Examples: haspp01eh1 -> P01-EH1, haspp09dif -> P09-DIF, hasnp64 -> P64.
_TANGO_HOST_PATTERN = re.compile(
    r"^has[a-z]?p(?P<beamline>\d{2})(?P<station>[a-z]+\d*[a-z]*)?$",
    re.IGNORECASE,
)


def infer_enclosure_tango(host: str | None) -> EnclosureHint:
    """Infer a candidate enclosure from a Tango DB host like haspp01eh1.

    Returns P<NN>-<STATION> when an endstation token is present (haspp01eh1 ->
    P01-EH1), or sector-only P<NN> when the host names just the beamline
    (hasnp64 -> P64). Always confirm=True; the host-to-enclosure mapping is a
    guess until a beamline confirms it.
    """
    if not host:
        return EnclosureHint(name=None, sector=None, station=None)
    bare = host.split(":", 1)[0]
    match = _TANGO_HOST_PATTERN.match(bare)
    if not match:
        return EnclosureHint(name=None, sector=None, station=None)
    beamline = f"P{match.group('beamline')}"
    station = match.group("station")
    if station:
        name = f"{beamline}-{station.upper()}"
        return EnclosureHint(name=name, sector=beamline, station=station)
    return EnclosureHint(name=beamline, sector=beamline, station=None)


@dataclass(frozen=True)
class PermissionGroup:
    """One user group from a *-bits user_group_permissions.yaml."""

    name: str
    allowed_plans: tuple[str, ...]
    allowed_devices: tuple[str, ...]
    forbidden_plans: tuple[str, ...] = field(default=())
    forbidden_devices: tuple[str, ...] = field(default=())


def parse_permissions(text: str) -> list[PermissionGroup]:
    """Parse a Bluesky queueserver user_group_permissions.yaml into groups."""
    try:
        raw = _lenient_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(raw, dict):
        return []
    groups_raw = raw.get("user_groups")
    if not isinstance(groups_raw, dict):
        return []

    def _strs(value: Any) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        return tuple(str(item) for item in value if item is not None)

    groups: list[PermissionGroup] = []
    for name, body in groups_raw.items():
        if not isinstance(body, dict):
            continue
        groups.append(
            PermissionGroup(
                name=str(name),
                allowed_plans=_strs(body.get("allowed_plans")),
                allowed_devices=_strs(body.get("allowed_devices")),
                forbidden_plans=_strs(body.get("forbidden_plans")),
                forbidden_devices=_strs(body.get("forbidden_devices")),
            )
        )
    return groups


@dataclass(frozen=True)
class MxcubeDevice:
    """One MXCuBE HardwareObjects config file (configuration/<beamline>/.../<name>.xml).

    Each file is an <object class="..."> describing one beamline device. The
    class is the mapping key (ExporterMotor, EMBLDetector, EMBLMiniDiff, ...).
    The control handle is whichever address the object carries: an Exporter
    address (host:port), a TINE name, an actuator name, or a server address.
    `rel_path` is the file path relative to the beamline config dir (e.g.
    eh1/detector-eiger16m), which carries the logical name and the endstation
    token. `model` and `device_type` are the vendor model when stated (a
    detector's <type>/<model>). Any field absent in the XML is None.
    """

    name: str
    obj_class: str
    rel_path: str
    handle: str | None
    device_type: str | None
    model: str | None
    is_mockup: bool


# MXCuBE control-handle child tags, in priority order. The first present one is
# the opaque control handle (the pv slot). exporter_address is host:port for the
# Exporter protocol; tinename is a TINE device address; actuator_name names an
# Exporter actuator; serverAddr is an EMBLMotorsGroup server path.
_MXCUBE_HANDLE_TAGS: tuple[str, ...] = (
    "exporter_address",
    "tinename",
    "actuator_name",
    "serverAddr",
    "username",
)


def _mxcube_handle(root: ET.Element) -> str | None:
    """Return the device's control handle from the first present handle tag.

    Looks at direct-child elements first (the common case: <exporter_address>,
    <actuator_name>, <serverAddr>), then falls back to a tinename= attribute on
    any descendant <channel>/<command> (the TINE detectors address their device
    that way rather than with a child tag).
    """
    for tag in _MXCUBE_HANDLE_TAGS:
        child = root.find(tag)
        if child is not None and child.text and child.text.strip():
            return child.text.strip()
    for element in root.iter():
        tinename = element.get("tinename")
        if tinename and tinename.strip():
            return tinename.strip()
    return None


def parse_mxcube_object(text: str, rel_path: str) -> MxcubeDevice | None:
    """Parse one MXCuBE HardwareObjects XML file into an MxcubeDevice.

    `rel_path` is the file path relative to the beamline config directory, with
    the .xml suffix already stripped (e.g. "eh1/detector-eiger16m"); its last
    segment is the logical name and its leading segment, when an endstation
    token, the enclosure. Returns None when the root is not an <object> or the
    XML is malformed, mirroring the lenient contract of the other parsers.
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    if root.tag != "object":
        return None
    obj_class = (root.get("class") or "").strip()
    if not obj_class:
        return None

    name = rel_path.rsplit("/", 1)[-1]
    device_type = _child_text(root, "type")
    model = _child_text(root, "model")
    is_mockup = "mockup" in obj_class.lower()

    return MxcubeDevice(
        name=name,
        obj_class=obj_class,
        rel_path=rel_path,
        handle=_mxcube_handle(root),
        device_type=device_type,
        model=model,
        is_mockup=is_mockup,
    )


def _mxcube_yaml_handle(spec: dict[str, Any]) -> str | None:
    """Return the device control handle from a YAML HardwareObjects object.

    The newer YAML format carries the control handle under an `epics:` block
    whose keys are the device PV prefixes (e.g. `MNC:B:PB05:m8`,
    `MNC:A:DCM01:`). We return the first prefix key, matching the "pv is the
    device prefix" convention the other extractors use (per-channel suffixes are
    axis-level detail left to human curation). Objects with no `epics:` block
    (mockups, pure software services, composite objects that only reference
    child files) have no handle.
    """
    epics = spec.get("epics")
    if isinstance(epics, dict):
        for prefix in epics:
            if isinstance(prefix, str) and prefix.strip():
                return prefix.strip()
    return None


def parse_mxcube_yaml_object(text: str, rel_path: str) -> MxcubeDevice | None:
    """Parse one MXCuBE HardwareObjects YAML file into an MxcubeDevice.

    The newer MXCuBE config format (used by e.g. Sirius Manaca) replaces the
    per-device `<object class="...">` XML with a YAML document carrying a
    top-level `class:` (a dotted module path like
    `LNLS.EPICS.EPICSMotor.LNLSRestrictedMotor`) and, for real devices, an
    `epics:` block of PV prefixes. This mirrors `parse_mxcube_object`: it returns
    the same MxcubeDevice shape so the mapper and emitter are source-agnostic.

    obj_class is the leaf class name (the last dotted segment), matching how the
    XML path carries a bare class and keeping the family-rule substring match
    meaningful. Returns None when the document is not a mapping or has no class,
    mirroring the lenient contract of the other parsers.
    """
    try:
        spec = _lenient_load(text)
    except yaml.YAMLError:
        return None
    if not isinstance(spec, dict):
        return None
    raw_class = spec.get("class")
    if not isinstance(raw_class, str) or not raw_class.strip():
        return None
    obj_class = raw_class.strip().rsplit(".", 1)[-1]

    name = rel_path.rsplit("/", 1)[-1]
    is_mockup = "mockup" in raw_class.lower()

    return MxcubeDevice(
        name=name,
        obj_class=obj_class,
        rel_path=rel_path,
        handle=_mxcube_yaml_handle(spec),
        device_type=None,
        model=None,
        is_mockup=is_mockup,
    )


# MXCuBE endstation tokens that appear as the leading path segment of a device's
# rel_path (eh1/detector.xml -> EH1). Anything else (a device at the beamline
# root, or under beamFocusingMotors/) has no endstation token.
_MXCUBE_ENDSTATION = re.compile(r"^(eh\d+|exp\d+|oh\d+)$", re.IGNORECASE)


def infer_enclosure_mxcube(rel_path: str, beamline: str) -> EnclosureHint:
    """Infer a candidate enclosure from an MXCuBE device's rel_path + beamline.

    A device under an endstation subdir (eh1/diff-omega) maps to
    <BEAMLINE>-<STATION> (P14-EH1); a device at the config root maps to the bare
    beamline (P14). Always confirm=True; the mapping is a guess until staff
    confirm it. `beamline` is the already-normalised beamline label (e.g. P14).
    """
    head = rel_path.split("/", 1)[0] if "/" in rel_path else ""
    if _MXCUBE_ENDSTATION.match(head):
        name = f"{beamline}-{head.upper()}"
        return EnclosureHint(name=name, sector=beamline, station=head)
    return EnclosureHint(name=beamline, sector=beamline, station=None)
