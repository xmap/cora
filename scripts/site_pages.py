"""Render a site descriptor into ONE reader-first facility page.

`render_all(site, slug=..., catalog_methods=..., beamlines=...)` returns a
{src_uri: markdown} dict with a single page, deployments/<slug>/index.md: a walk
through what the facility gives an experiment, organized by the reader's journey
(techniques -> resources -> safety envelope -> who acts), not one page per bounded
context. Tables appear inside reader-shaped sections with framing prose, mirroring
the beamline layout page's per-subsystem device tables.

The facility's human title is `facility.heading` when set, else the upper-cased
`display_name` (which equals `code`); the bound beamlines are passed in by the
build hook as (label, slug) pairs so the page links to whichever beamlines the
site actually hosts.

A Practice method links to the generated Catalog Methods page only when the
catalog defines it (threaded in as `catalog_methods`); methods still pending in
the catalog render unlinked.

The mkdocs on_files hook in scripts/mkdocs_hooks.py injects this as a virtual
file at build time; nothing is written to disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from site_descriptor import Site

_BLOB_BASE = "https://github.com/xmap/cora/blob/main"
MODEL_PAGE = "../../architecture/model.md"
METHODS_PAGE = "../../catalog/methods.md"


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


def _planned(labels: list[str]) -> list[str]:
    if not labels:
        return []
    return ["*Planned: " + ", ".join(labels) + ".*"]


def _facility(
    site: Site,
    *,
    slug: str,
    site_label: str,
    beamlines: list[tuple[str, str]],
    primary: str | None,
) -> list[str]:
    f = site.facility
    rows = [["Facility code", f"`{f.code}`"], ["Kind", f"`{f.kind}`"]]
    if f.institution:
        rows.append(["Institution", f.institution])
    if f.sectors:
        rows.append(["Sectors", ", ".join(f"`{s}`" for s in f.sectors)])
    if beamlines:
        rows.append(
            ["Beamlines", ", ".join(f"[{label}](../{bslug}/index.md)" for label, bslug in beamlines)]
        )
    run_clause = f" {primary} runs at" if primary else " its beamlines run at"
    exp_clause = f"a {primary} experiment" if primary else "an experiment"
    return [
        f"{site_label} is the synchrotron site{run_clause}. This page is the home for the "
        f"facility-level facts {exp_clause} inherits but does not own: the techniques adapted here, "
        "the resources a run draws on, the safety envelope it clears, and the people and agents who "
        "act in it. The beamline links up to these rather than restating them.",
        _banner(slug),
        _table(["Property", "Value"], rows),
    ]


def _techniques(
    site: Site, catalog_methods: frozenset[str], *, site_label: str, run_label: str
) -> list[str]:
    def _method(name: str) -> str:
        return f"[`{name}`]({METHODS_PAGE})" if name in catalog_methods else f"`{name}`"

    active = [[f"`{p.name}`", _method(p.method)] for p in site.practices if not p.pending]
    pending = [p.name for p in site.practices if p.pending]
    blocks = [
        "## The techniques adapted here",
        f"A Practice is {site_label}'s facility-tuned form of a cross-facility [Method]({MODEL_PAGE}): "
        "the ISA-88 Site Recipe layer. The Method names a technique abstractly in the Catalog; the "
        f"Practice is how {run_label} runs it here. Each row links up to the Method it adapts.",
        _table(["Practice", "Method"], active),
    ]
    blocks += _planned(pending)
    return blocks


def _resources(site: Site) -> list[str]:
    active = [[f"`{s.name}`", f"`{s.kind}`"] for s in site.supplies if not s.pending]
    pending = [s.name for s in site.supplies if s.pending]
    blocks = [
        "## The resources you draw on",
        "Supplies are the continuously-available facility resources a run needs present before it "
        "can start: beam, cooling, vacuum. The facility tracks their availability; a run's "
        "required supplies are checked at the pre-flight gate.",
        _table(["Supply", "Kind"], active),
    ]
    blocks += _planned(pending)
    return blocks


def _safety(site: Site) -> list[str]:
    active = [
        [f"`{c.name}`", f"`{c.kind}`", c.binding or ""] for c in site.clearances if not c.pending
    ]
    pending = [c.name for c in site.clearances if c.pending]
    blocks = [
        "## The safety envelope",
        "Before an experiment runs, it clears the facility's safety forms (Clearances), and "
        "operators carry forward hazards and quirks as Cautions. Both gate or advise the work "
        "without being part of the measurement itself.",
        _table(["Clearance", "Kind", "Binds"], active),
    ]
    blocks += _planned(pending)
    active_cautions = [c for c in site.cautions if not c.pending]
    if active_cautions:
        lines = []
        for c in active_cautions:
            tag = f"**{c.severity}**" if c.severity else "**Caution**"
            lines.append(f"- {tag} ({c.target}): {c.text}")
        blocks.append("**Active cautions**\n" + "\n".join(lines))
    pending_cautions = [c.text for c in site.cautions if c.pending]
    blocks += _planned(pending_cautions)
    return blocks


def _principals(site: Site, *, site_label: str) -> list[str]:
    actor_active = [[a.name, f"`{a.kind}`"] for a in site.actors if not a.pending]
    actor_pending = [a.name for a in site.actors if a.pending]
    agent_rows = [
        [f"`{a.name}`", f"`{a.version}`", f"`{a.model_provider} / {a.model_name}`"]
        for a in site.agents
        if not a.pending
    ]
    agent_pending = [a.name for a in site.agents if a.pending]
    blocks = [
        "## Who acts here",
        f"Every action CORA records is attributed to a principal. At {site_label} those are the "
        "people registered facility-wide (the operator on shift, safety reviewers, proposal PIs) "
        "and the autonomous agents. Human display names live in `actor_profile` (the editable, "
        "forgettable layer), not in the event-sourced Actor record, which carries only id and kind.",
        _table(["Person or service", "Kind"], actor_active),
    ]
    blocks += _planned(actor_pending)
    blocks += [
        "Agents are principals too. Each one's id is shared with an Access Actor (`kind=agent`) "
        "through a single cross-BC atomic write, so an agent's writes attribute the same way a "
        "person's do. The agents active here today are advisory: they observe and write Decisions, "
        "and never gate Run state. The planned agents are deterministic and rule-based; when "
        "enabled they act only by issuing a command the spine already exposes, through the same "
        "authorized path a person uses.",
        _table(["Agent", "Version", "Model"], agent_rows),
    ]
    blocks += _planned(agent_pending)
    return blocks


def _modeled(
    site_label: str, *, facility_code: str, beamlines: list[tuple[str, str]]
) -> list[str]:
    blocks = [
        f"## How {site_label} is modeled",
        f"{site_label} itself is not an Asset: it is a Federation `Facility` with "
        f'`FacilityKind = Site` (`facility_code = "{facility_code}"`). The beamlines it hosts are '
        "the root Assets (`tier = Unit`, `parent_id = None`), each bound to the Site directly by "
        f"`facility_code`. See [the CORA model]({MODEL_PAGE}) for the aggregate shapes.",
    ]
    if beamlines:
        rows = [
            [f"`{label}`", "`Unit`", f"`{facility_code}`", f"[{label}](../{bslug}/index.md)"]
            for label, bslug in beamlines
        ]
        blocks.append(_table(["Asset", "Tier", "facility_code", "Hosts"], rows))
    blocks.append(
        "Sub-systems and devices nested under a beamline are Assets with `tier = Component` or "
        "`tier = Device`, linked via `parent_id`. Being non-root, they do not carry `facility_code`; "
        "they inherit facility scope through the `parent_id` tree."
    )
    return blocks


def render_all(
    site: Site,
    *,
    slug: str = "aps",
    catalog_methods: frozenset[str] = frozenset(),
    beamlines: list[tuple[str, str]] | None = None,
) -> dict[str, str]:
    f = site.facility
    site_label = f.heading or f.display_name.upper()
    if beamlines is None:
        beamlines = [(b, b.lower()) for b in f.beamlines]
    # A single-beamline site reads naturally in the singular ("X runs at"); a
    # site hosting several (APS hosts 2-BM and 19-BM) uses neutral phrasing so
    # no one beamline is privileged by glob order.
    primary = beamlines[0][0] if len(beamlines) == 1 else None
    run_label = primary or "the beamline"

    blocks = [f"# {site_label}"]
    blocks += _facility(site, slug=slug, site_label=site_label, beamlines=beamlines, primary=primary)
    blocks += _techniques(site, catalog_methods, site_label=site_label, run_label=run_label)
    blocks += _resources(site)
    blocks += _safety(site)
    blocks += _principals(site, site_label=site_label)
    blocks += _modeled(site_label, facility_code=f.code, beamlines=beamlines)
    return {f"deployments/{slug}/index.md": "\n\n".join(blocks) + "\n"}
