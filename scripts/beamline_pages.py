"""Render a beamline descriptor into a docs page.

`render_all(descriptor)` returns a {src_uri: markdown} dict (mirroring the
contract scripts/scenarios_pages.render_all used) with a single generated page,
deployments/2-bm/beamline.md: the layout walk source to detector, one section
per subsystem, a device table per group, then the cross-cutting controls and resources.

The mkdocs on_files hook in scripts/mkdocs_hooks.py injects these as virtual
files at build time; nothing is written to disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from beamline_descriptor import BeamlineDescriptor, Device, Group

PAGE_SRC_URI = "deployments/2-bm/beamline.md"
DESCRIPTOR_BLOB_URL = "https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml"

# Links up to the cross-facility Catalog (relative to the layout page).
_CATALOG_FAMILIES = "../../catalog/families.md"
_CATALOG_MODELS = "../../catalog/models.md"

# Populated per render from the catalog so a family/model only becomes a link
# when it actually exists in the Catalog; pending/local ones render as plain text.
_KNOWN_FAMILIES: frozenset[str] = frozenset()
_KNOWN_MODELS: frozenset[str] = frozenset()

# Structural device fields rendered in dedicated columns or handled explicitly,
# so they are not repeated as open key-specs.
_STRUCTURAL = frozenset(
    {
        "name",
        "family",
        "pv",
        "model",
        "controller",
        "replaceable",
        "passive",
        "new",
        "confirm",
        "note",
        "drawing",
        "calibrations",
        "constituents",
        "enclosure",
    }
)


def render_all(
    descriptor: BeamlineDescriptor,
    *,
    catalog_families: frozenset[str] = frozenset(),
    catalog_models: frozenset[str] = frozenset(),
) -> dict[str, str]:
    global _KNOWN_FAMILIES, _KNOWN_MODELS
    _KNOWN_FAMILIES = catalog_families
    _KNOWN_MODELS = catalog_models
    return {PAGE_SRC_URI: _render_page(descriptor)}


def _esc(text: str) -> str:
    return text.replace("|", r"\|")


def _catalog_link(name: str, known: frozenset[str], page: str) -> str:
    """Link to a Catalog page only when the name exists there; else plain code."""
    return f"[`{name}`]({page})" if name in known else f"`{name}`"


def _humanize(key: str) -> str:
    return key.replace("-", " ").replace("_", " ").strip().capitalize()


def _admonition(text: str, *, kind: str = "note", title: str | None = None) -> str:
    head = f'!!! {kind} "{title}"' if title else f"!!! {kind}"
    body = "\n".join(f"    {line}" for line in text.strip().splitlines())
    return f"{head}\n{body}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_esc(cell) if cell else "" for cell in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _pv_cell(pv: str | dict[str, Any] | None) -> str:
    if pv is None:
        return ""
    if isinstance(pv, str):
        return f"`{pv}`"
    parts: list[str] = []
    for key, value in pv.items():
        if isinstance(value, list):
            rendered = ", ".join(f"`{item}`" for item in value)
        else:
            rendered = f"`{value}`"
        parts.append(f"{key}: {rendered}")
    return "<br>".join(parts)


def _permit_signal_cell(permit_signal: str | dict[str, Any] | None) -> str:
    """Render an Enclosure's permit signal: a PV string, or a confirm note."""
    if permit_signal is None:
        return ""
    if isinstance(permit_signal, str):
        return f"`{permit_signal}`"
    note = permit_signal.get("confirm")
    if note:
        return f"confirm: {note}"
    return ""


def _specs_cell(device: Device) -> str:
    parts: list[str] = []
    if device.passive:
        parts.append("passive")
    if device.model:
        parts.append(f"model {_catalog_link(device.model, _KNOWN_MODELS, _CATALOG_MODELS)}")
    if device.controller:
        parts.append(f"via `{device.controller}`")
    for key, value in (device.model_extra or {}).items():
        if key in _STRUCTURAL or value is None or value is False:
            continue
        label = key.replace("_", " ")
        if value is True:
            parts.append(label)
        elif isinstance(value, list):
            parts.append(f"{label}: " + ", ".join(str(item) for item in value))
        else:
            parts.append(f"{label}: {value}")
    if device.drawing is not None:
        rev = f" rev {device.drawing.revision}" if device.drawing.revision else ""
        parts.append(f"drawing: {device.drawing.system} {device.drawing.number}{rev}")
    for cal in device.calibrations:
        meta: list[str] = []
        if cal.status:
            meta.append(str(cal.status))
        if cal.operating_point:
            meta.append(", ".join(f"{k}={v}" for k, v in cal.operating_point.items()))
        suffix = f" ({'; '.join(meta)})" if meta else ""
        parts.append(f"calibration: {cal.quantity} = {cal.value}{suffix}")
    if isinstance(device.confirm, str) and device.confirm:
        parts.append(f"confirm: {device.confirm}")
    if device.note:
        parts.append(device.note)
    return "<br>".join(parts)


def _status_cell(device: Device) -> str:
    parts: list[str] = []
    if device.new:
        parts.append("`new`")
    if device.confirm:
        parts.append("`confirm`")
    return " ".join(parts)


def _device_rows(devices: list[Device]) -> list[list[str]]:
    return [
        [
            f"`{d.name}`",
            _catalog_link(d.family, _KNOWN_FAMILIES, _CATALOG_FAMILIES) if d.family else "",
            _pv_cell(d.pv),
            _specs_cell(d),
            "yes" if d.replaceable else "",
            _status_cell(d),
        ]
        for d in devices
    ]


_DEVICE_HEADERS = ["Name", "Family", "PV", "Key specs", "Replaceable", "Status"]


def _device_table(devices: list[Device]) -> str:
    return _table(_DEVICE_HEADERS, _device_rows(devices))


def _render_group(name: str, group: Group) -> str:
    blocks: list[str] = [f"## {_humanize(name)}"]
    if group.intro:
        blocks.append(group.intro.strip())

    extra = group.model_extra or {}
    captions: list[str] = []
    if group.enclosure:
        captions.append(f"Enclosure: {group.enclosure}.")
    if isinstance(extra.get("cora"), str):
        captions.append(f"CORA: {extra['cora']}.")
    if isinstance(extra.get("placement"), str):
        captions.append(f"Placement: {extra['placement']}.")
    if captions:
        blocks.append("*" + " ".join(captions) + "*")

    if group.note:
        blocks.append(_admonition(group.note))

    if group.devices:
        blocks.append(_device_table(group.devices))
        for device in group.devices:
            if device.constituents:
                blocks.append(f"**{device.name} constituents**")
                blocks.append(_device_table(device.constituents))

    if group.decommissioned:
        joined = ", ".join(group.decommissioned)
        blocks.append(f"**Decommissioned (provenance):** {joined}")

    return "\n\n".join(blocks)


def _render_controls(controls: Any) -> str:
    blocks: list[str] = ["## Controls"]
    if controls.intro:
        blocks.append(controls.intro.strip())
    if controls.motion_controllers:
        blocks.append("### Motion controllers")
        blocks.append(_device_table(controls.motion_controllers))
    if controls.triggering:
        blocks.append("### Triggering")
        blocks.append(_device_table(controls.triggering))
    if controls.software_iocs_not_modeled:
        joined = ", ".join(controls.software_iocs_not_modeled)
        blocks.append(
            _admonition(
                f"{joined}\n\nThese are software processes, referenced by PV "
                "prefix in the Plan and Method wiring layer, never registered "
                "as Assets.",
                title="Software IOCs (not modeled as Assets)",
            )
        )
    return "\n\n".join(blocks)


def _render_resources(resources: Any) -> str:
    blocks: list[str] = ["## Resources"]
    if resources.intro:
        blocks.append(resources.intro.strip())
    if resources.supplies:
        blocks.append("### Supplies")
        kinds = [str(item.get("kind", item)) for item in resources.supplies]
        blocks.append("\n".join(f"- {kind}" for kind in kinds))
    if resources.replaceable_parts:
        blocks.append("### Replaceable parts")
        for key, values in resources.replaceable_parts.items():
            joined = ", ".join(str(item) for item in values)
            blocks.append(f"**{_humanize(key)}:** {joined}")
    return "\n\n".join(blocks)


def _render_page(descriptor: BeamlineDescriptor) -> str:
    beamline = descriptor.beamline
    blocks: list[str] = ["# Source"]

    blocks.append(
        "The incident beam, produced, conditioned, and defined before the sample. "
        "A walk along the source-stage devices; the sample and detection stages are "
        "documented as their own composed-fixture pages. Each device pairs its human "
        "name with the EPICS handle, its key specs, and whether it is field "
        "replaceable. `new` marks a device not yet modeled in CORA; `confirm` "
        "marks a value taken from the docs that staff have not yet verified."
    )
    blocks.append(
        _admonition(
            f"This page is generated from the descriptor at "
            f"[`deployments/2-bm/beamline.yaml`]({DESCRIPTOR_BLOB_URL}). "
            "Edit the descriptor, not this page. For the CORA Asset model, "
            "settings, vendor catalog, drawings, and wiring, see "
            "[Inventory](inventory.md).",
            kind="info",
            title="Generated from the descriptor",
        )
    )

    extra = beamline.model_extra or {}
    facts: list[list[str]] = []
    for label, value in (
        ("Facility", beamline.facility),
        ("Sector", beamline.sector),
        ("Tier", beamline.tier),
        ("Drawing", beamline.drawing),
        ("Source", beamline.source),
    ):
        if value:
            cell = str(value)
            if label == "Source" and extra.get("source_confirm"):
                cell += f" (confirm: {extra['source_confirm']})"
            facts.append([label, cell])
    if beamline.z_span_mm and len(beamline.z_span_mm) == 2:
        zcell = f"{beamline.z_span_mm[0]} to {beamline.z_span_mm[1]} mm"
        if extra.get("z_span_confirm"):
            zcell += " (confirm)"
        facts.append(["Z span", zcell])
    if facts:
        blocks.append(_table(["Property", "Value"], facts))

    if descriptor.enclosures:
        rows = [
            [
                f"`{e.name}`",
                e.role or "",
                f"`{e.facility_code}`" if e.facility_code else "",
                _permit_signal_cell(e.permit_signal),
            ]
            for e in descriptor.enclosures
        ]
        blocks.append("## Enclosures")
        blocks.append(_table(["Enclosure", "Role", "Facility", "Permit signal"], rows))

    # Only the source stage renders as the generated walk; the sample and
    # detection stages are the composed-fixture pages (equipment/sample_tower,
    # equipment/microscope).
    for name, group in descriptor.groups:
        if group.stage != "source":
            continue
        blocks.append(_render_group(name, group))

    if descriptor.controls is not None:
        blocks.append(_render_controls(descriptor.controls))
    if descriptor.resources is not None:
        blocks.append(_render_resources(descriptor.resources))

    return "\n\n".join(blocks) + "\n"
