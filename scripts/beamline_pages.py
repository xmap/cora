"""Render a beamline descriptor into a docs page.

`render_all(descriptor)` returns a {src_uri: markdown} dict (mirroring the
contract scripts/scenarios_pages.render_all used) with a single generated page:
2-BM's Source-stage walk (front-end optics to the sample), one section per
subsystem with a device table per group. 2-BM hand-authors everything else
(index, sample, detector, controls, operations, ...); this is the one page
generated from the descriptor, so it cannot silently drift from what the
source-stage devices actually are.

This module used to also generate a beamline's whole reader set (index,
inventory, the sample/detector/controls beam-walk) for "model-tier" beamlines:
CORA's further modeled-but-not-deployed beamlines, reverse-engineered from
public source. That corpus moved to the private xmap/descriptors repo, and the
generator went with the reasoning that moved it: cora's own domain model "only
contains what at least one real deployment forced into it" (docs/deployments/
index.md), and the same now holds for this generator. 2-BM is the only
descriptor cora carries, and it is not model-tier, so that code had no real
input left to run against. Recoverable from git history if a second real
deployment ever needs it.

The mkdocs on_files hook in scripts/mkdocs_hooks.py injects this as a virtual
file at build time; nothing is written to disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from beamline_descriptor import BeamlineDescriptor, Device, Group

_BLOB_BASE = "https://github.com/xmap/cora/blob/main"

# Links up to the cross-facility Catalog. The relative depth differs by where the
# page sits: a page at deployments/<slug>/ (beamline.md, inventory.md, and the
# stages-layout source.md / sample.md / detector.md / controls.md) needs "../../";
# a page at deployments/<slug>/equipment/ needs "../../../". Set per render via
# _set_catalog_depth, mirroring how _KNOWN_FAMILIES is set per render.
_CATALOG_FAMILIES = "../../catalog/families.md"
_CATALOG_MODELS = "../../catalog/models.md"


def _set_catalog_depth(prefix: str) -> None:
    """Point the Catalog links at the right relative depth for the page being
    rendered. `prefix` is the hops from the page to the docs root (e.g. "../../"
    for a deployments/<slug>/ page, "../../../" for a .../equipment/ page)."""
    global _CATALOG_FAMILIES, _CATALOG_MODELS
    _CATALOG_FAMILIES = f"{prefix}catalog/families.md"
    _CATALOG_MODELS = f"{prefix}catalog/models.md"

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
    slug: str = "2-bm",
    catalog_families: frozenset[str] = frozenset(),
    catalog_models: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Render the beamline's one generated page: its Source-stage walk.

    `page_layout: stages` (2-BM's layout) generates a flat `source.md` sibling
    of the hand-authored pages; `page_layout: walk` generates `beamline.md`
    instead, with the walk-layout framing in its intro (no current descriptor
    uses it, but nothing here assumes stages is the only valid choice).
    """
    global _KNOWN_FAMILIES, _KNOWN_MODELS
    _KNOWN_FAMILIES = catalog_families
    _KNOWN_MODELS = catalog_models
    blob_url = f"{_BLOB_BASE}/deployments/{slug}/beamline.yaml"
    layout = descriptor.beamline.page_layout

    if layout == "stages":
        return {
            f"deployments/{slug}/source.md": _render_page(
                descriptor,
                slug=slug,
                blob_url=blob_url,
                link_inventory=False,
                flat=True,
                show_source_ref=True,
            ),
        }

    return {
        f"deployments/{slug}/beamline.md": _render_page(
            descriptor, slug=slug, blob_url=blob_url, show_source_ref=True
        )
    }


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


def _enclosures_blocks(descriptor: BeamlineDescriptor) -> list[str]:
    """The beamline-scoped Enclosures table (empty when the descriptor has none).

    A beamline-wide spatial fact: every stage sits inside one of these hutches,
    so the table belongs at beamline scope. In the stages layout it renders on
    the index; in the walk layout it stays on the Source page.
    """
    if not descriptor.enclosures:
        return []
    rows = [
        [
            f"`{e.name}`",
            e.role or "",
            f"`{e.facility_code}`" if e.facility_code else "",
            _permit_signal_cell(e.permit_signal),
        ]
        for e in descriptor.enclosures
    ]
    return [
        "## Enclosures",
        _table(["Enclosure", "Role", "Facility", "Permit signal"], rows),
    ]


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
    body = _render_group_body(group)
    return f"## {_humanize(name)}" + ("\n\n" + body if body else "")


def _render_group_body(group: Group) -> str:
    blocks: list[str] = []
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


def _render_page(
    descriptor: BeamlineDescriptor,
    *,
    slug: str,
    blob_url: str,
    link_inventory: bool = True,
    include_enclosures: bool = True,
    flat: bool = False,
    show_source_ref: bool = False,
) -> str:
    # Both beamline.md (walk layout) and the flat source.md (stages layout) sit
    # at deployments/<slug>/, so the catalog depth is the same for each.
    _set_catalog_depth("../../")
    beamline = descriptor.beamline
    blocks: list[str] = ["# Source"]

    if flat:
        # Stages layout: the stages are first-class sibling pages, so the intro
        # orients to the source stage itself and links Controls as a sibling. No
        # "walk" framing and no composed-fixture / Operations references (those
        # are walk-layout concepts and Operations is not a page here).
        intro = (
            "The incident beam, produced, conditioned, and defined before the sample. "
            "The controllers that drive these devices are on the [Controls](controls.md) "
            "page. Each device pairs its human name with its control handle, its key "
            "specs, and whether it is field replaceable. `new` marks a device not yet "
            "modeled in CORA; `confirm` marks a value taken from the docs that staff have "
            "not yet verified."
        )
    else:
        intro = (
            "The incident beam, produced, conditioned, and defined before the sample. "
            "A walk along the source-stage devices; the sample and detection stages are "
            "documented as their own composed-fixture pages, the controllers that drive "
            "these devices are on the Controls page, and the supplies they draw on are in "
            "Operations. Each device pairs its human name with its control handle, its key "
            "specs, and whether it is field replaceable. `new` marks a device not yet "
            "modeled in CORA; `confirm` marks a value taken from the docs that staff have "
            "not yet verified."
        )
    blocks.append(intro)
    banner = (
        f"This page is generated from the descriptor at "
        f"[`deployments/{slug}/beamline.yaml`]({blob_url}). "
        "Edit the descriptor, not this page."
    )
    if link_inventory:
        banner += (
            " For the CORA Asset model, settings, vendor catalog, drawings, and "
            "wiring, see [Inventory](inventory.md)."
        )
    # A pilot has no generated index, so its Source page is the only place the
    # source-repo pointer can land; a model-tier beamline shows it on the index.
    ref = descriptor.beamline.source_ref
    if show_source_ref and ref is not None:
        banner += f"\n\nSource: [{ref.label}]({ref.url})."
    blocks.append(
        _admonition(banner, kind="info", title="Generated from the descriptor")
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

    if include_enclosures:
        blocks.extend(_enclosures_blocks(descriptor))

    # Only the source stage renders as the generated walk; the sample and
    # detection stages are the composed-fixture pages (equipment/sample_tower,
    # equipment/microscope).
    for name, group in descriptor.groups:
        if group.stage != "source":
            continue
        blocks.append(_render_group(name, group))

    return "\n\n".join(blocks) + "\n"
