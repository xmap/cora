"""Expand `beamline:*` markers on deployment pages from the beamline descriptor.

Deployment pages keep their hand-authored, reader-first narrative but mark the
factual, drift-prone tables (device specs, controller wiring, PVs) with paired
HTML comments whose body the build renders from deployments/<id>/beamline.yaml:

    <!-- beamline:controllers -->
    ...regenerable table the build overwrites...
    <!-- /beamline:controllers -->

The on_page_markdown hook in scripts/mkdocs_hooks.py calls `expand_markers` for
every deployments/ page that carries a marker, passing the loaded descriptor for
that deployment. Each marker body is replaced with a table rendered from the
descriptor, so the facts cannot drift from the single source of truth. An unknown
kind, an unknown/missing arg, an unpaired marker, or an empty render raises
BeamlineMarkerError, which aborts `mkdocs build` regardless of the mkdocs
`strict:` flag (so local and CI behave the same).

This is the deployment-tier counterpart of scripts/architecture_pages.py, which
does the same for architecture/ pages from the introspected code model.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from beamline_descriptor import BeamlineDescriptor, Device

REPO_BLOB = "https://github.com/xmap/cora/blob/main/"

# Controllers list both real motion controllers and the passive chassis that
# houses them; only the MotionController family renders as a driven-box row.
_MOTION_CONTROLLER_FAMILY = "MotionController"

# The beam-path stages a calibrations marker can scope to (mirrors
# beamline_descriptor.BEAM_PATH_STAGES; an unknown stage fails the build).
_STAGES = frozenset({"source", "sample", "detection"})


class BeamlineMarkerError(ValueError):
    """A beamline marker is malformed, unknown, or renders empty."""


def _source_note(slug: str) -> str:
    """The "generated from the descriptor" admonition prepended to each table,
    the per-table counterpart of the banner on the generated beamline.md page."""
    url = f"{REPO_BLOB}deployments/{slug}/beamline.yaml"
    return (
        '!!! info "Generated from the descriptor"\n'
        f"    This table is generated from [`deployments/{slug}/beamline.yaml`]({url}). "
        "Edit the descriptor, not this table."
    )


def _esc(text: str) -> str:
    return text.replace("|", r"\|")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_esc(c) if c else "" for c in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _driven_by(descriptor: BeamlineDescriptor, controller_name: str) -> list[str]:
    """Device names whose `controller` back-reference points at this controller.

    Derived by inverting the back-reference rather than hand-listed, so the
    Drives column tracks the descriptor and cannot drift. Walks each group's
    devices and their nested constituents in authored beam order.
    """
    names: list[str] = []

    def _walk(devices: list[Device] | None) -> None:
        for device in devices or []:
            if device.controller == controller_name:
                names.append(device.name)
            _walk(device.constituents)

    for _key, group in descriptor.groups:
        _walk(group.devices)
    return names


def _spec(device: Device, key: str) -> str | None:
    value = (device.model_extra or {}).get(key)
    return None if value is None else str(value)


def render_controllers(descriptor: BeamlineDescriptor, _args: dict[str, str]) -> str:
    """The motion-controller table: one row per MotionController drive box.

    The Drives column is derived from the driven devices' `controller`
    back-reference; the chassis (a Housing) is excluded.
    """
    controls = descriptor.controls
    if controls is None:
        raise BeamlineMarkerError("beamline:controllers: descriptor has no controls section")

    rows: list[list[str]] = []
    for controller in controls.motion_controllers:
        if controller.family != _MOTION_CONTROLLER_FAMILY:
            continue
        driven = _driven_by(descriptor, controller.name)
        drives = ", ".join(f"`{name}`" for name in driven)
        protocol = _spec(controller, "protocol")
        axes = _spec(controller, "axis_count")
        handle = _spec(controller, "epics_handle")
        rows.append(
            [
                f"`{controller.name}`",
                drives,
                f"`{controller.model}`" if controller.model else "",
                f"`{protocol}`" if protocol else "",
                axes or "",
                f"`{handle}`" if handle else "",
            ]
        )
    if not rows:
        raise BeamlineMarkerError("beamline:controllers: no MotionController rows to render")
    return _table(["Controller", "Drives", "Model", "Protocol", "Axes", "EPICS handle"], rows)


def _permit_signal(permit_signal: object) -> str:
    """Render an Enclosure permit signal: a PV string, or a confirm note."""
    if permit_signal is None:
        return ""
    if isinstance(permit_signal, str):
        return f"`{permit_signal}`"
    if isinstance(permit_signal, dict):
        note = permit_signal.get("confirm")
        if note:
            return f"confirm: {note}"
    return ""


def render_enclosures(descriptor: BeamlineDescriptor, _args: dict[str, str]) -> str:
    """The access-gated volumes (hutches) and the permit PV that gates each.

    The Gates column is derived from the beam-path groups that name each
    enclosure, and the permit signal is the descriptor's `permit_signal`, so the
    permit PVs (the drift-prone bit a wrong value would break) track the source.
    """
    if not descriptor.enclosures:
        raise BeamlineMarkerError("beamline:enclosures: descriptor has no enclosures")

    rows: list[list[str]] = []
    for enclosure in descriptor.enclosures:
        gates = ", ".join(
            f"`{key}`" for key, group in descriptor.groups if group.enclosure == enclosure.name
        )
        rows.append(
            [
                f"`{enclosure.name}`",
                (enclosure.role or "").replace("-", " "),
                f"`{enclosure.facility_code}`" if enclosure.facility_code else "",
                gates,
                _permit_signal(enclosure.permit_signal),
            ]
        )
    return _table(["Enclosure", "Role", "Anchored to", "Gates", "Permit signal"], rows)


def _operating_point(point: dict[str, object] | None) -> str:
    if not point:
        return ""
    return ", ".join(f"{key}={value}" for key, value in point.items())


def render_calibrations(descriptor: BeamlineDescriptor, args: dict[str, str]) -> str:
    """The empirical calibrations recorded on a stage's devices.

    One row per Calibration, sourced from the device's `calibrations`, so the
    values (the drift-prone bit, e.g. an objective magnification) track the
    descriptor. Scoped to a `stage` so a page renders only its own devices.
    """
    stage = args["stage"]
    if stage not in _STAGES:
        raise BeamlineMarkerError(
            f"beamline:calibrations: unknown stage {stage!r}; expected one of {sorted(_STAGES)}"
        )

    rows: list[list[str]] = []

    def _walk(devices: list[Device] | None) -> None:
        for device in devices or []:
            for cal in device.calibrations:
                rows.append(
                    [
                        f"`{device.name}`",
                        f"`{cal.quantity}`",
                        "" if cal.value is None else str(cal.value),
                        _operating_point(cal.operating_point),
                        cal.status or "",
                        cal.source or "",
                    ]
                )
            _walk(device.constituents)

    for _key, group in descriptor.groups:
        if group.stage == stage:
            _walk(group.devices)
    if not rows:
        raise BeamlineMarkerError(f"beamline:calibrations: no calibrations at stage {stage!r}")
    return _table(
        ["Device", "Quantity", "Value", "Operating point", "Status", "Source"], rows
    )


RENDERERS = {
    "controllers": render_controllers,
    "calibrations": render_calibrations,
    "enclosures": render_enclosures,
}
REQUIRED_ARGS: dict[str, frozenset[str]] = {
    "controllers": frozenset(),
    "calibrations": frozenset({"stage"}),
    "enclosures": frozenset(),
}
OPTIONAL_ARGS: dict[str, frozenset[str]] = {
    "controllers": frozenset(),
    "calibrations": frozenset(),
    "enclosures": frozenset(),
}

_MARKER_RE = re.compile(
    r"<!--\s*beamline:(?P<kind>[a-z][a-z0-9-]*)(?P<args>(?:\s+[a-z_]+=[^\s>]+)*)\s*-->"
    r"(?P<body>.*?)"
    r"<!--\s*/beamline:(?P=kind)\s*-->",
    re.DOTALL,
)


def _parse_args(kind: str, raw: str, src_uri: str) -> dict[str, str]:
    args: dict[str, str] = {}
    for token in raw.split():
        key, _, value = token.partition("=")
        args[key] = value
    allowed = REQUIRED_ARGS[kind] | OPTIONAL_ARGS[kind]
    unknown = set(args) - allowed
    if unknown:
        raise BeamlineMarkerError(f"{src_uri}: beamline:{kind} has unknown args {sorted(unknown)}")
    missing = REQUIRED_ARGS[kind] - set(args)
    if missing:
        raise BeamlineMarkerError(
            f"{src_uri}: beamline:{kind} missing required args {sorted(missing)}"
        )
    return args


def expand_markers(markdown: str, *, descriptor: BeamlineDescriptor, src_uri: str) -> str:
    """Replace every `beamline:*` marker body with a table rendered from the
    descriptor. Raises BeamlineMarkerError on any malformed, unknown, unpaired,
    or empty-rendering marker so the build fails loudly."""
    matched = 0
    slug = src_uri.split("/")[1] if "/" in src_uri else src_uri
    note = _source_note(slug)

    def _repl(m: re.Match[str]) -> str:
        nonlocal matched
        matched += 1
        kind = m.group("kind")
        if kind not in RENDERERS:
            raise BeamlineMarkerError(f"{src_uri}: unknown beamline marker kind {kind!r}")
        args = _parse_args(kind, m.group("args"), src_uri)
        body = RENDERERS[kind](descriptor, args)
        if not body:
            raise BeamlineMarkerError(f"{src_uri}: beamline:{kind} rendered empty")
        open_marker = f"<!-- beamline:{kind}{m.group('args')} -->"
        close_marker = f"<!-- /beamline:{kind} -->"
        return f"{open_marker}\n{note}\n\n{body}\n{close_marker}"

    out = _MARKER_RE.sub(_repl, markdown)
    opens = len(re.findall(r"<!--\s*beamline:", markdown))
    closes = len(re.findall(r"<!--\s*/beamline:", markdown))
    if opens != matched or closes != matched:
        raise BeamlineMarkerError(
            f"{src_uri}: malformed or unpaired beamline marker "
            f"(open={opens}, close={closes}, matched={matched})"
        )
    return out
