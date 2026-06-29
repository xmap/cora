"""Map parsed *-bits devices onto candidate CORA deployment facts.

The Family suggestion is deliberately conservative: only confident cases map to a
real catalog Family. Everything else carries the ophyd class name and a confirm
flag, because Family graduation and naming are human, naming-r3-gated decisions.
The recurrence report (emit.py) is what actually argues for graduating a Family.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .parse import (
    DeviceInstance,
    EnclosureHint,
    OphydSketch,
    TangoDevice,
    infer_enclosure,
    infer_enclosure_tango,
)

# Confident class-or-substring to CORA Family mappings. Keys are matched against
# the ophyd class name (case-insensitive substring). Order matters: first hit wins.
_FAMILY_RULES: tuple[tuple[str, str], ...] = (
    ("ad_creator", "Camera"),
    ("detectorcam", "Camera"),
    ("areadetector", "Camera"),
    ("pseudosingle", "PseudoAxis"),
    ("pseudopositioner", "PseudoAxis"),
    ("undulator", "InsertionDevice"),
    ("monochromator", "Monochromator"),
    ("slit", "Slit"),
    ("shutter", "Shutter"),
    ("mirror", "Mirror"),
    ("scintillator", "Scintillator"),
    ("scaler", "GenericProbe"),
)

# Labels that hint at a CORA Role. Functional labels only; station labels (4idb,
# 8ide) are handled separately as enclosure hints.
_ROLE_LABELS: dict[str, str] = {
    "motor": "Positioner",
    "stage": "Positioner",
    "detector": "Detector",
    "detectors": "Detector",
    "area_detector": "Detector",
    "scaler": "Detector",
    "shutter": "Controller",
    "slit": "Positioner",
}

# Labels and class hints that bucket a device into one of the three CORA beam-path
# stages. The bucketing is a placeholder; the candidate flags grouping as confirm.
_DETECTION_HINTS: frozenset[str] = frozenset(
    {"detector", "detectors", "area_detector", "camera", "scaler", "diode"}
)
_SAMPLE_HINTS: frozenset[str] = frozenset({"sample", "stage", "goniometer"})

_STATION_LABEL = re.compile(r"^\d+(?:bm|id)[a-z]$")


@dataclass(frozen=True)
class CandidateDevice:
    """A draft CORA device derived from one *-bits instance."""

    name: str
    family: str
    family_confirmed: bool
    pv: str | dict[str, str] | None
    labels: tuple[str, ...]
    role_hints: tuple[str, ...]
    enclosure: str | None
    stage: str
    source_class: str
    confirm_reasons: tuple[str, ...]
    is_sim: bool


def suggest_family(instance: DeviceInstance) -> tuple[str, bool]:
    """Return (family, confirmed). Confirmed is False when we fall back to the class name."""
    haystack = f"{instance.class_path} {instance.class_name}".lower()
    for needle, family in _FAMILY_RULES:
        if needle in haystack:
            return family, True
    return instance.class_name, False


def _axis_map_from_kwargs(instance: DeviceInstance) -> dict[str, str]:
    """Resolve axis suffixes carried in the YAML kwargs (pv_* and motorsDict).

    Many FormattedComponent devices pass their per-axis suffixes through the
    devices.yml entry (Transfocator pv_lens1, polar motorsDict), so the axes are
    recoverable from the instance even when the class itself is not static.
    """
    prefix = instance.prefix or ""
    axes: dict[str, str] = {}
    motors_dict = instance.kwargs.get("motorsDict")
    if isinstance(motors_dict, dict):
        for axis, suffix in motors_dict.items():
            axes[str(axis)] = f"{prefix}{suffix}"
    for key, value in instance.kwargs.items():
        if key.startswith("pv_") and isinstance(value, str | int):
            axes[key[len("pv_") :]] = f"{prefix}{value}"
    return axes


def _axis_map_from_sketch(instance: DeviceInstance, sketch: OphydSketch) -> dict[str, str]:
    prefix = instance.prefix or ""
    return {
        axis.name: f"{prefix}{axis.suffix}"
        for axis in sketch.axes
        if axis.resolved and axis.kind == "motor"
    }


def _build_pv(
    instance: DeviceInstance, sketch: OphydSketch | None
) -> tuple[str | dict[str, str] | None, list[str]]:
    reasons: list[str] = []
    axes = _axis_map_from_kwargs(instance)
    if not axes and sketch is not None:
        axes = _axis_map_from_sketch(instance, sketch)
    if axes:
        if len(axes) == 1:
            return next(iter(axes.values())), reasons
        return dict(sorted(axes.items())), reasons
    if instance.prefix:
        reasons.append("axes unresolved: pv is the device prefix, per-axis PVs need confirm")
        return instance.prefix, reasons
    reasons.append("no prefix and no resolvable axes")
    return None, reasons


def _enclosure(instance: DeviceInstance) -> EnclosureHint:
    for label in instance.labels:
        if _STATION_LABEL.match(label):
            return infer_enclosure(label)
    return infer_enclosure(instance.prefix)


def _stage(instance: DeviceInstance, family: str) -> str:
    tokens = {label.lower() for label in instance.labels}
    tokens.add(family.lower())
    tokens.add(instance.class_name.lower())
    if tokens & _DETECTION_HINTS or "camera" in family.lower():
        return "detection"
    if tokens & _SAMPLE_HINTS:
        return "sample"
    return "source"


def _role_hints(instance: DeviceInstance) -> tuple[str, ...]:
    hints = {_ROLE_LABELS[label] for label in instance.labels if label in _ROLE_LABELS}
    return tuple(sorted(hints))


def to_candidate_device(instance: DeviceInstance, sketch: OphydSketch | None) -> CandidateDevice:
    """Join one devices.yml instance with its ophyd class sketch into a candidate."""
    family, family_confirmed = suggest_family(instance)
    pv, pv_reasons = _build_pv(instance, sketch)
    enclosure_hint = _enclosure(instance)

    reasons: list[str] = list(pv_reasons)
    if not family_confirmed:
        reasons.append(
            f"family is the ophyd class name {instance.class_name!r}; needs a CORA Family"
        )
    if enclosure_hint.name is None:
        reasons.append("enclosure unresolved from prefix or labels")
    if instance.is_factory:
        reasons.append("factory device (ad_creator): plugins and file paths need a human")
    if sketch is not None:
        reasons.extend(sketch.confirm_reasons)
    elif not instance.is_sim:
        reasons.append(f"ophyd class {instance.class_name!r} not found in devices/*.py")

    return CandidateDevice(
        name=instance.name,
        family=family,
        family_confirmed=family_confirmed,
        pv=pv,
        labels=instance.labels,
        role_hints=_role_hints(instance),
        enclosure=enclosure_hint.name,
        stage=_stage(instance, family),
        source_class=instance.class_path,
        confirm_reasons=tuple(dict.fromkeys(reasons)),
        is_sim=instance.is_sim,
    )


# DESY OnlineXML mapping (PETRA III, Tango).
#
# Confident Tango-class/role to CORA Family rules. Matched as a case-insensitive
# substring against the Tango module then the role type; first hit wins. Kept
# conservative on purpose: bare motor controllers (oms58, motor_tango) cannot be
# told linear-vs-rotary from the module alone, so they fall through to the module
# name unconfirmed, exactly as unknown ophyd classes do on the EPICS path.
_TANGO_FAMILY_RULES: tuple[tuple[str, str], ...] = (
    ("pilatus", "Camera"),
    ("lambda", "Camera"),
    ("eiger", "Camera"),
    ("pco", "Camera"),
    ("perkinelmer", "Camera"),
    ("maia", "Camera"),
    ("lom", "Monochromator"),
    ("mca", "GenericProbe"),
    ("xmcd", "GenericProbe"),
    ("e6c", "Diffractometer"),
    ("diffractomet", "Diffractometer"),
)

# Role types worth modelling. Everything not listed is bookkeeping (counters,
# timers, ADC/DAC, IO registers, the measurement_group summary rows) and is
# filtered out of the candidate, though still counted by the caller.
_TANGO_MODELLABLE_TYPES: frozenset[str] = frozenset(
    {
        "motor",
        "stepping_motor",
        "mca",
        "detector",
        "diffractometer",
        "diffractometercontroller",
        "type_tango",
        "motosam_tiltr",
    }
)

# Role-type and family hints that bucket a Tango device into a beam-path stage.
_TANGO_DETECTION_TYPES: frozenset[str] = frozenset({"mca", "detector"})
_TANGO_SAMPLE_HINTS: frozenset[str] = frozenset(
    {"diffractometer", "diffractometercontroller", "motosam_tiltr"}
)


def suggest_family_tango(device: TangoDevice) -> tuple[str, bool]:
    """Return (family, confirmed). Confirmed is False when we fall back to the module."""
    haystack = f"{device.module or ''} {device.type or ''}".lower()
    for needle, family in _TANGO_FAMILY_RULES:
        if needle in haystack:
            return family, True
    return device.module or device.type or device.name, False


def is_modellable_tango(device: TangoDevice) -> bool:
    """True when the device is a modellable instrument, not bookkeeping IO."""
    return (device.type or "").lower() in _TANGO_MODELLABLE_TYPES


def _tango_stage(device: TangoDevice, family: str) -> str:
    role = (device.type or "").lower()
    if role in _TANGO_DETECTION_TYPES or "camera" in family.lower():
        return "detection"
    if role in _TANGO_SAMPLE_HINTS or "diffractometer" in family.lower():
        return "sample"
    return "source"


def to_candidate_device_tango(device: TangoDevice) -> CandidateDevice | None:
    """Map one OnlineXML TangoDevice to a candidate, or None if it is filtered.

    Returns None for bookkeeping IO (counters, timers, registers, measurement
    groups) so the caller can count what was dropped. The pv slot carries the
    Tango device address (the opaque control handle); the Tango DB host is kept
    as a confirm reason since the host-to-enclosure mapping is a guess.
    """
    if not is_modellable_tango(device):
        return None

    family, family_confirmed = suggest_family_tango(device)
    enclosure_hint = infer_enclosure_tango(device.host)

    reasons: list[str] = []
    if device.address is None:
        reasons.append("no Tango address in the registry row; control handle needs confirm")
    if not family_confirmed:
        reasons.append(
            f"family is the Tango module {family!r}; linear-vs-rotary and the CORA Family need a human"
        )
    if device.host:
        reasons.append(f"Tango host {device.host!r}; endstation to enclosure is a guess")
    if enclosure_hint.name is None:
        reasons.append("enclosure unresolved from Tango host")
    reasons.append(
        "axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human"
    )

    return CandidateDevice(
        name=device.name,
        family=family,
        family_confirmed=family_confirmed,
        pv=device.address,
        labels=(),
        role_hints=(),
        enclosure=enclosure_hint.name,
        stage=_tango_stage(device, family),
        source_class=device.module or "unknown-tango-module",
        confirm_reasons=tuple(dict.fromkeys(reasons)),
        is_sim=False,
    )
