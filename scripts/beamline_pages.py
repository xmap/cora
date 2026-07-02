"""Render a beamline descriptor into a docs page.

`render_all(descriptor)` returns a {src_uri: markdown} dict (mirroring the
contract scripts/scenarios_pages.render_all used) with a single generated page,
deployments/2-bm/beamline.md: the Source page, a walk along the source-stage
devices (front-end optics to the sample), one section per subsystem with a device
table per group. The cross-cutting controllers and supplies are their own pages
(equipment/controls.md, operations.md); the descriptor still carries them for the
tests and the future seeder.

The mkdocs on_files hook in scripts/mkdocs_hooks.py injects these as virtual
files at build time; nothing is written to disk.
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
    facility_label: str | None = None,
    control_plane: str | None = None,
    model_tier: bool = False,
) -> dict[str, str]:
    """Render a beamline's generated docs pages.

    Every beamline gets the Source-stage walk (`beamline.md`). A model-tier
    beamline (a reverse-engineered / design scaffold, not one of the richly
    hand-authored pilots) additionally gets its whole reader set generated from
    the descriptor: the front-door `index.md`, the `inventory.md` reference, and
    the Sample / Detector / Controls beam-walk pages. The pilots pass
    model_tier=False and keep their hand-authored set; only their Source walk is
    generated, as before.

    A model-tier beamline with `page_layout: stages` (the SRX pilot) uses a
    flattened set instead: Inventory is dissolved into flat `source.md`,
    `sample.md`, `detector.md`, and `controls.md` siblings (no `equipment/`
    folder, no `inventory.md`), with `index.md` linking them directly.
    """
    global _KNOWN_FAMILIES, _KNOWN_MODELS
    _KNOWN_FAMILIES = catalog_families
    _KNOWN_MODELS = catalog_models
    blob_url = f"{_BLOB_BASE}/deployments/{slug}/beamline.yaml"
    layout = descriptor.beamline.page_layout

    if layout == "stages":
        # Stages layout: the generated Source page sits flat at source.md. A
        # model-tier beamline's whole reader set is generated (index + the flat
        # stage pages); a pilot hand-authors index / sample / detector / controls
        # and their rich operational pages, so only its Source page generates.
        pages = {
            f"deployments/{slug}/source.md": _render_page(
                descriptor,
                slug=slug,
                blob_url=blob_url,
                link_inventory=False,
                include_enclosures=not model_tier,
                flat=True,
                show_source_ref=not model_tier,
            ),
        }
        if model_tier:
            pages[f"deployments/{slug}/index.md"] = _render_index(
                descriptor,
                slug=slug,
                facility_label=facility_label,
                control_plane=control_plane,
                page_layout=layout,
            )
            pages.update(
                _render_beamwalk(
                    descriptor, slug=slug, control_plane=control_plane, prefix="", depth="../../"
                )
            )
        return pages

    pages = {
        f"deployments/{slug}/beamline.md": _render_page(
            descriptor, slug=slug, blob_url=blob_url, show_source_ref=not model_tier
        )
    }
    if model_tier:
        pages[f"deployments/{slug}/index.md"] = _render_index(
            descriptor, slug=slug, facility_label=facility_label, control_plane=control_plane
        )
        pages[f"deployments/{slug}/inventory.md"] = _render_inventory(
            descriptor, slug=slug, blob_url=blob_url
        )
        pages.update(_render_beamwalk(descriptor, slug=slug, control_plane=control_plane))
    return pages


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


# ---------------------------------------------------------------------------
# Model-tier reader pages, generated from the descriptor.
#
# A model beamline's whole reader set is generated so it cannot drift or carry
# engineering-internal bookkeeping (rule-of-three, loose-family graduation,
# tracking tags). The set is beamline-natural: a front door, then the beam walk
# (source to detector) plus controls. The default "walk" layout keeps the full
# asset tree as a separate Inventory reference; the "stages" layout dissolves
# Inventory into the flat source/sample/detector/controls stage pages.
# ---------------------------------------------------------------------------

_STAGE_FILE = {"sample": "sample.md", "detection": "detector.md"}
_STAGE_TITLE = {"sample": "Sample", "detection": "Detector"}


def _confirm_clause(descriptor: BeamlineDescriptor) -> str:
    beamline = descriptor.beamline
    if beamline.evidence == "live":
        return ""
    if beamline.evidence == "controls_config":
        return (
            " The device handles are read from the facility's public controls configuration and "
            "verified against it; vendor parts, energies, and physical positions are not in it and "
            "are carried `confirm` until beamline staff verify them."
        )
    if beamline.evidence == "design_report":
        return (
            " The values are read from the beamline's design report and carried `confirm` until "
            "staff verify them against the built instrument."
        )
    return (
        " The device families are inferred from public facility pages and papers; no control "
        "handles or vendor models are public, so every value is carried `confirm` until staff "
        "verify it."
    )


def _render_index(
    descriptor: BeamlineDescriptor,
    *,
    slug: str,
    facility_label: str | None,
    control_plane: str | None,
    page_layout: str = "walk",
) -> str:
    beamline = descriptor.beamline
    extra = beamline.model_extra or {}
    name = beamline.name or slug
    summary = beamline.summary or ""
    blocks: list[str] = [f"# {name}"]
    if summary:
        cov = " A deliberately partial first cut." if beamline.coverage == "partial" else ""
        blocks.append(f"*{summary}.{cov}*")

    # Facts table: identity + seam, all from the descriptor.
    facility_cell = beamline.facility or ""
    if facility_label:
        facility_cell = f"[{facility_label}](../{beamline.facility}/index.md)"
        if control_plane:
            facility_cell += f" ({control_plane})"
    facts: list[list[str]] = [["Facility", facility_cell]]
    if beamline.sector:
        facts.append(["Sector", str(beamline.sector)])
    src = str(beamline.source) if beamline.source else ""
    if src:
        facts.append(["Source", src])
    facts.append(
        ["Modelled", f"{_MATURITY[beamline.maturity]}, {_COVERAGE[beamline.coverage]} coverage"]
    )
    blocks.append(_table(["Property", "Value"], facts))

    # The provenance caveat (how trustworthy the facts are, keyed on evidence
    # tier) folds into the generated-from banner rather than a near-identical
    # "What CORA models" section; the enclosures it used to name are in the
    # table below.
    banner = (
        f"This page is generated from the descriptor at "
        f"[`deployments/{slug}/beamline.yaml`]({_BLOB_BASE}/deployments/{slug}/beamline.yaml). "
        "Edit the descriptor, not this page."
    )
    caveat = _confirm_clause(descriptor).strip()
    ref = beamline.source_ref
    if ref is not None:
        # Name the specific public source the facts were read from, alongside the
        # evidence-tier caveat.
        caveat = (caveat + " ").lstrip() + f"Source: [{ref.label}]({ref.url})."
    if caveat:
        banner += "\n\n" + caveat
    blocks.append(_admonition(banner, kind="info", title="Generated from the descriptor"))

    stages = {g.stage for _n, g in descriptor.groups}
    flat = page_layout == "stages"

    # Enclosures are a beamline-wide spatial fact (every stage sits in a hutch),
    # so the stages layout carries the table on the index rather than the Source
    # page. The walk layout keeps it on the Source page (see _render_page).
    if flat:
        blocks.extend(_enclosures_blocks(descriptor))

    if flat:
        # Stages layout: the stages are first-class sibling pages, so present
        # them as a section list (in beam order, controls last) rather than a
        # one-line walk sentence. No Inventory (the stage pages are the tree).
        # The optional one-line shape leads the section when authored.
        lead = beamline.shape.strip() if beamline.shape else "The devices along the beam, area by area."
        section = ["## The beamline", lead]
        bullets = ["- [Source](source.md): the beam, produced and conditioned before the sample."]
        if "sample" in stages:
            bullets.append("- [Sample](sample.md): the sample environment and its positioning.")
        if "detection" in stages:
            bullets.append("- [Detector](detector.md): what records the beam after the sample.")
        bullets.append("- [Controls](controls.md): the control plane CORA's edge conducts over.")
        section.append("\n".join(bullets))
        blocks.append("\n\n".join(section))
    else:
        # Walk layout: the beam walk as a one-line spine, linking the equipment/
        # pages and pointing at the Inventory reference for the full device tree.
        walk_links = ["[Source](beamline.md)"]
        if "sample" in stages:
            walk_links.append("[Sample](equipment/sample.md)")
        if "detection" in stages:
            walk_links.append("[Detector](equipment/detector.md)")
        walk_links.append("[Controls](equipment/controls.md)")
        walk_sentence = (
            "The instrument, area by area along the beam: "
            + " to ".join(walk_links[:-1])
            + f", driven by {walk_links[-1]}."
            + " The full device tree, with families and control handles, is the "
            "[Inventory](inventory.md)."
        )
        blocks.append("## Walk the beam\n\n" + walk_sentence)

    blocks.append("## More")
    blocks.append(
        "- [Techniques](techniques.md): what the beamline is for.\n"
        "- [Governance](governance.md): who acts, and the trust shape that gates them.\n"
        "- [Open questions](questions.md): the world-facts CORA needs staff to confirm."
    )
    return "\n\n".join(blocks) + "\n"


_MATURITY = {"pilot": "operational pilot", "design": "in design", "model": "reverse-engineered"}
_COVERAGE = {"full": "full", "partial": "partial"}


def _render_inventory(descriptor: BeamlineDescriptor, *, slug: str, blob_url: str) -> str:
    _set_catalog_depth("../../")  # deployments/<slug>/inventory.md
    beamline = descriptor.beamline
    name = beamline.name or slug
    blocks: list[str] = ["# Inventory"]
    blocks.append(
        f"*The CORA Asset model for the operational core of {name}: every device by beam-path "
        "stage, its Family and control handle, and what still needs confirming.*"
    )
    blocks.append(
        _admonition(
            f"Generated from [`deployments/{slug}/beamline.yaml`]({blob_url}). "
            "Edit the descriptor, not this page.",
            kind="info",
            title="Generated from the descriptor",
        )
    )
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

    # All device groups, in beam-path order, each as its device table.
    for stage in ("source", "sample", "detection"):
        for gname, group in descriptor.groups:
            if group.stage == stage:
                blocks.append(_render_group(gname, group))
    if descriptor.controls is not None:
        controls_devices = [
            *descriptor.controls.motion_controllers,
            *descriptor.controls.triggering,
        ]
        if controls_devices:
            blocks.append("## Controls")
            if descriptor.controls.intro:
                blocks.append(descriptor.controls.intro.strip())
            blocks.append(_device_table(controls_devices))
    return "\n\n".join(blocks) + "\n"


def _render_beamwalk(
    descriptor: BeamlineDescriptor,
    *,
    slug: str,
    control_plane: str | None,
    prefix: str = "equipment/",
    depth: str = "../../../",
) -> dict[str, str]:
    # `prefix`/`depth` place the stage pages: the default "equipment/" +
    # "../../../" is the walk layout; the stages layout passes "" + "../../" so
    # the pages are flat siblings of index.md.
    pages: dict[str, str] = {}
    _set_catalog_depth(depth)
    # Sample + Detector: one page per stage, its groups rendered.
    for stage, filename in _STAGE_FILE.items():
        groups = [(n, g) for n, g in descriptor.groups if g.stage == stage]
        if not groups:
            continue
        blocks = [f"# {_STAGE_TITLE[stage]}"]
        # A single group whose name is just the stage would render a `##` heading
        # duplicating the page title; render its body inline instead.
        if len(groups) == 1 and _humanize(groups[0][0]) == _STAGE_TITLE[stage]:
            blocks.append(_render_group_body(groups[0][1]))
        else:
            for gname, group in groups:
                blocks.append(_render_group(gname, group))
        pages[f"deployments/{slug}/{prefix}{filename}"] = "\n\n".join(blocks) + "\n"

    # Controls: the cross-cutting drive electronics + the seam sentence.
    controls = descriptor.controls
    cblocks = ["# Controls"]
    seam = "The control plane the beamline runs on, and the seam CORA's edge conducts over."
    if control_plane:
        seam += f" Control plane: {control_plane}."
    cblocks.append(seam)
    if controls is not None:
        if controls.intro:
            cblocks.append(controls.intro.strip())
        devices = [*controls.motion_controllers, *controls.triggering]
        if devices:
            cblocks.append(_device_table(devices))
    pages[f"deployments/{slug}/{prefix}controls.md"] = "\n\n".join(cblocks) + "\n"
    return pages
