"""Map parsed *-bits devices onto candidate CORA deployment facts.

The Family suggestion is deliberately conservative: only confident cases map to a
real catalog Family. Everything else carries the ophyd class name and a confirm
flag, because Family graduation and naming are human, naming-r3-gated decisions.
The recurrence report (emit.py) is what actually argues for graduating a Family.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .parse import DeviceInstance, EnclosureHint, OphydSketch, infer_enclosure

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
