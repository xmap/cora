"""Parse *-bits sources: Guarneri devices.yml, ophyd device classes, PV grammar.

Pure functions over text; no network, no cora.* imports. Anything that cannot be
resolved statically is recorded as a confirm reason rather than guessed, so the
emitter can flag it. ophyd_async modules are detected and skipped (their device
trees are not class-attribute Cpt trees, so the static oracle does not apply).
"""

from __future__ import annotations

import ast
import re
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


_LenientLoader.add_multi_constructor("tag:yaml.org,2002:python/name:", _construct_python_name)
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
        bases = tuple(name for name in (_call_name(base) for base in node.bases) if name)
        axes, reasons = _class_axes(node)
        if module_async:
            reasons = (*reasons, "ophyd_async module: device tree not statically parseable")
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
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("ophyd_async"):
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
            reasons.append(f"{target.id}: FormattedComponent suffix resolved at runtime")
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
            return EnclosureHint(name=name, sector=f"{sector}-{branch_label}", station=station)
        return EnclosureHint(name=None, sector=f"{sector}-{branch_label}", station=None)
    return EnclosureHint(name=None, sector=None, station=None)


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
