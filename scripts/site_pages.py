"""Render a site descriptor into ONE reader-first facility page.

`render_all(site, slug=..., catalog_methods=..., beamlines=...)` returns a
{src_uri: markdown} dict with a single page, deployments/<slug>/index.md.

The page is adaptive and roster-first. Its spine is the beamline roster (the
Site's fleet, with each beamline's badges and one-line summary read from its
descriptor, so the facility page never duplicates the landing page by hand).
Around the roster, a section renders ONLY when the Site has real content for it:
a thin Site (one modelled beamline, placeholder governance) shows the facts
header, the roster, its distinctive supplies, and a one-line modelling pointer,
and omits the techniques / governance / cautions sections entirely rather than
render empty tables. The operational pilot (APS), which has real practices,
staffed principals, agents, and cautions, shows them all.

The facility's human title is `facility.heading` when set, else the upper-cased
`display_name` (which equals `code`).

A Practice method links to the generated Catalog Methods page only when the
catalog defines it (threaded in as `catalog_methods`); methods still pending in
the catalog render unlinked.

The mkdocs on_files hook in scripts/mkdocs_hooks.py injects this as a virtual
file at build time; nothing is written to disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from site_descriptor import Site

_BLOB_BASE = "https://github.com/xmap/cora/blob/main"
MODEL_PAGE = "../../architecture/model.md"
METHODS_PAGE = "../../catalog/methods.md"

# Badge enum value -> display word, mirroring the landing-page table cells.
_MATURITY_CELL = {"pilot": "Pilot", "design": "Design", "model": "Model"}
_EVIDENCE_CELL = {
    "live": "Live",
    "design_report": "Design report",
    "controls_config": "Controls config",
    "narrative": "Narrative",
}
_COVERAGE_CELL = {"full": "Full", "partial": "Partial"}

# The maturity roll-up: the fleet role a Site's page leads with, strongest first.
# A Site is a pilot if it drives any beamline live, else on the roadmap if any
# beamline is in design, else an off-roadmap generalization exercise.
_FLEET_ROLE = {
    "pilot": "Operational pilot",
    "design": "Roadmap (in design)",
    "model": "Off-roadmap generalization",
}

# Supply kinds every storage-ring Site provides; mentioned in one trailing clause
# rather than listed as rows, so the supplies section surfaces only the
# Site-distinctive resources (a second source, a cryogen for a magnet, ...).
_BOILERPLATE_SUPPLY_KINDS = frozenset({"PhotonBeam", "CoolingWater", "Vacuum"})


@dataclass(frozen=True)
class BeamlineRef:
    """A hosted beamline as the facility roster needs it: its label and slug for
    the link, its three badges, and its one-line summary, all read from the
    beamline descriptor by the mkdocs hook."""

    label: str
    slug: str
    maturity: str
    evidence: str
    coverage: str
    summary: str


def _esc(text: str) -> str:
    return text.replace("|", r"\|")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_esc(cell) if cell else "" for cell in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _banner(slug: str) -> str:
    blob = f"{_BLOB_BASE}/deployments/{slug}/site.yaml"
    return (
        '!!! info "Generated from the site descriptor"\n'
        f"    This page is generated from [`deployments/{slug}/site.yaml`]({blob}). "
        "Edit the descriptor, not this page."
    )


def _fleet_role(beamlines: list[BeamlineRef]) -> str:
    maturities = {b.maturity for b in beamlines}
    if "pilot" in maturities:
        return _FLEET_ROLE["pilot"]
    if "design" in maturities:
        return _FLEET_ROLE["design"]
    return _FLEET_ROLE["model"]


def _facts_header(
    site: Site, *, slug: str, site_label: str, beamlines: list[BeamlineRef]
) -> list[str]:
    f = site.facility
    rows = [["Facility code", f"`{f.code}`"]]
    if f.institution:
        rows.append(["Institution", f.institution])
    if f.control_plane:
        rows.append(["Control plane", f.control_plane])
    if beamlines:
        rows.append(["Fleet role", _fleet_role(beamlines)])
        rows.append(["Beamlines", str(len(beamlines))])
    if f.sectors:
        rows.append(["Sectors", ", ".join(f"`{s}`" for s in f.sectors)])
    return [
        f"{site_label} is a Federation `Facility` (`FacilityKind = Site`): the home for the "
        "facility-level facts an experiment inherits but does not own. The beamlines it hosts "
        "link up to this page rather than restating it.",
        _banner(slug),
        _table(["Property", "Value"], rows),
    ]


def _roster(beamlines: list[BeamlineRef], *, site_label: str, note: str | None) -> list[str]:
    if not beamlines:
        return []
    rows = [
        [
            f"[{b.label}](../{b.slug}/index.md)",
            _MATURITY_CELL.get(b.maturity, b.maturity),
            _EVIDENCE_CELL.get(b.evidence, b.evidence),
            _COVERAGE_CELL.get(b.coverage, b.coverage),
            b.summary,
        ]
        for b in beamlines
    ]
    blocks = [
        "## The beamlines",
        f"What CORA models at {site_label}. Each row's badges and one-line summary are read from "
        "the beamline's own descriptor; follow the link for the full model.",
        _table(["Beamline", "Maturity", "Evidence", "Coverage", "What it is"], rows),
    ]
    if note:
        blocks.append(f"*{note}*")
    return blocks


def _techniques(
    site: Site, catalog_methods: frozenset[str], *, site_label: str, run_label: str
) -> list[str]:
    def _method(name: str) -> str:
        return f"[`{name}`]({METHODS_PAGE})" if name in catalog_methods else f"`{name}`"

    active = [[f"`{p.name}`", _method(p.method)] for p in site.practices if not p.pending]
    pending = [p.name for p in site.practices if p.pending]
    if not active:
        # Nothing earned yet: a one-line planned note (or nothing) beats an
        # empty table. Thin Sites simply omit the techniques section.
        if pending:
            return [
                "## The techniques adapted here",
                f"*Planned: {len(pending)} facility Practices, each adapting a cross-facility "
                f"[Method]({MODEL_PAGE}); none earned into the model yet.*",
            ]
        return []
    blocks = [
        "## The techniques adapted here",
        f"A Practice is {site_label}'s facility-tuned form of a cross-facility "
        f"[Method]({MODEL_PAGE}): the ISA-88 Site Recipe layer. The Method names a technique "
        "abstractly in the Catalog; the Practice is how "
        f"{run_label} runs it here. Each row links up to the Method it adapts.",
        _table(["Practice", "Method"], active),
    ]
    if pending:
        blocks.append(f"*Planned: {len(pending)} further Practices.*")
    return blocks


def _resources(site: Site) -> list[str]:
    # Split the boilerplate storage-ring supplies (beam / cooling / vacuum) from
    # the Site-distinctive ones. Only render the section for the distinctive
    # resources; the boilerplate is acknowledged in a single clause.
    distinctive = [s for s in site.supplies if s.kind not in _BOILERPLATE_SUPPLY_KINDS]
    boilerplate = [s for s in site.supplies if s.kind in _BOILERPLATE_SUPPLY_KINDS]
    if not distinctive:
        return []
    intro = (
        "Beyond the shared beam, cooling, and vacuum every Site provides, "
        if boilerplate
        else ""
    )
    lines = ["## What this Site provides", f"{intro}CORA's model tracks these facility resources:"]
    for s in distinctive:
        tail = f": {s.note}" if s.note else ""
        pend = " *(pending)*" if s.pending else ""
        lines.append(f"- **{s.name}** (`{s.kind}`){pend}{tail}")
    return lines


def _governance(site: Site, *, site_label: str) -> list[str]:
    clr_active = [
        [f"`{c.name}`", f"`{c.kind}`", c.binding or ""] for c in site.clearances if not c.pending
    ]
    clr_pending = [c.name for c in site.clearances if c.pending]
    actor_active = [[a.name, f"`{a.kind}`"] for a in site.actors if not a.pending]
    agent_active = [
        [f"`{a.name}`", f"`{a.version}`", f"`{a.model_provider} / {a.model_name}`"]
        for a in site.agents
        if not a.pending
    ]
    agent_pending = [a.name for a in site.agents if a.pending]

    # A thin Site has only placeholder governance (a pending PSS, two pending
    # actor rows, no agents). Collapse that to one honest sentence rather than
    # three empty tables.
    has_real = bool(clr_active or actor_active or agent_active)
    if not has_real:
        parts = []
        if clr_pending:
            parts.append(f"gated by the facility safety system ({', '.join(clr_pending)}, pending)")
        parts.append("the principal roster is pending")
        if not agent_active:
            parts.append("no autonomous agents run here today")
        return [
            "## Safety and governance",
            f"Access at {site_label} is " + "; ".join(parts) + ".",
        ]

    blocks = ["## Safety and governance"]
    if clr_active:
        blocks += [
            "Before an experiment runs it clears the facility's safety forms (Clearances).",
            _table(["Clearance", "Kind", "Binds"], clr_active),
        ]
    if clr_pending:
        blocks.append(f"*Planned clearances: {', '.join(clr_pending)}.*")
    if actor_active:
        blocks += [
            "Every action CORA records is attributed to a principal registered facility-wide; "
            "human display names live in `actor_profile`, not the event-sourced Actor record.",
            _table(["Person or service", "Kind"], actor_active),
        ]
    if agent_active:
        blocks += [
            "Agents are principals too: each shares its id with an Access Actor (`kind=agent`) "
            "so its writes attribute like a person's. Active agents are advisory (they observe "
            "and write Decisions, never gate Run state).",
            _table(["Agent", "Version", "Model"], agent_active),
        ]
    if agent_pending:
        blocks.append(
            f"*Planned agents: {', '.join(agent_pending)} (deterministic, rule-based; when enabled "
            "they act only through a command the spine already exposes).*"
        )
    return blocks


def _cautions(site: Site) -> list[str]:
    active = [c for c in site.cautions if not c.pending]
    pending = [c for c in site.cautions if c.pending]
    if not active and not pending:
        return []
    blocks = ["## Active cautions"]
    if active:
        blocks.append(
            "Hazards and quirks operators carry forward; they advise or gate work without being "
            "part of the measurement."
        )
        lines = []
        for c in active:
            tag = f"**{c.severity}**" if c.severity else "**Caution**"
            lines.append(f"- {tag} ({c.target}): {c.text}")
        blocks.append("\n".join(lines))
    if pending:
        blocks.append(f"*Planned: {len(pending)} further cautions under confirmation.*")
    return blocks


def _modeled(site_label: str, *, facility_code: str) -> list[str]:
    return [
        "## How this maps to CORA's model",
        f"{site_label} is a Federation `Facility` (`FacilityKind = Site`, "
        f'`facility_code = "{facility_code}"`); the beamlines above are its root Assets '
        f"(`tier = Unit`), and their sub-systems nest below by `parent_id`. See "
        f"[the CORA model]({MODEL_PAGE}) for the aggregate shapes.",
    ]


def render_all(
    site: Site,
    *,
    slug: str = "aps",
    catalog_methods: frozenset[str] = frozenset(),
    beamlines: list[BeamlineRef] | None = None,
) -> dict[str, str]:
    f = site.facility
    site_label = f.heading or f.display_name.upper()
    if beamlines is None:
        beamlines = []
    # Order the roster by the facility's declared beamline list (a meaningful
    # order the Site chose), not the glob order the hook discovered them in.
    # Any beamline not named in the declared list sorts to the end, by label.
    if f.beamlines:
        rank = {name: i for i, name in enumerate(f.beamlines)}
        beamlines = sorted(beamlines, key=lambda b: (rank.get(b.label, len(rank)), b.label))
    run_label = beamlines[0].label if len(beamlines) == 1 else "the beamline"

    blocks = [f"# {site_label}"]
    blocks += _facts_header(site, slug=slug, site_label=site_label, beamlines=beamlines)
    blocks += _roster(beamlines, site_label=site_label, note=f.beamlines_note)
    blocks += _techniques(site, catalog_methods, site_label=site_label, run_label=run_label)
    blocks += _resources(site)
    blocks += _governance(site, site_label=site_label)
    blocks += _cautions(site)
    blocks += _modeled(site_label, facility_code=f.code)
    return {f"deployments/{slug}/index.md": "\n\n".join(b for b in blocks if b) + "\n"}
