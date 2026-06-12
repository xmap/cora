"""Render the site descriptor into ONE reader-first APS page.

`render_all(site, catalog_methods=...)` returns a {src_uri: markdown} dict with a
single page, deployments/aps/index.md: a walk through what the facility gives an
experiment, organized by the reader's journey (techniques -> resources -> safety
envelope -> who acts), not one page per bounded context. Tables appear inside
reader-shaped sections with framing prose, mirroring the beamline layout page's
per-subsystem device tables.

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

SITE_BLOB_URL = "https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml"
MODEL_PAGE = "../../architecture/model.md"
METHODS_PAGE = "../../catalog/methods.md"


def _esc(text: str) -> str:
    return text.replace("|", r"\|")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_esc(cell) if cell else "" for cell in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _banner() -> str:
    return (
        '!!! info "Generated from the site descriptor"\n'
        f"    This page is generated from [`deployments/aps/site.yaml`]({SITE_BLOB_URL}). "
        "Edit the descriptor, not this page."
    )


def _planned(labels: list[str]) -> list[str]:
    if not labels:
        return []
    return ["*Planned: " + ", ".join(labels) + ".*"]


def _facility(site: Site) -> list[str]:
    f = site.facility
    rows = [["Facility code", f"`{f.code}`"], ["Kind", f"`{f.kind}`"]]
    if f.institution:
        rows.append(["Institution", f.institution])
    if f.sectors:
        rows.append(["Sectors", ", ".join(f"`{s}`" for s in f.sectors)])
    if f.beamlines:
        rows.append(["Beamlines", ", ".join(f"[{b}](../2-bm/index.md)" for b in f.beamlines)])
    return [
        "APS is the synchrotron site 2-BM runs at. This page is the home for the facility-level "
        "facts a 2-BM experiment inherits but does not own: the techniques adapted here, the "
        "resources a run draws on, the safety envelope it clears, and the people and agents who "
        "act in it. The beamline links up to these rather than restating them.",
        _banner(),
        _table(["Property", "Value"], rows),
    ]


def _techniques(site: Site, catalog_methods: frozenset[str]) -> list[str]:
    def _method(name: str) -> str:
        return f"[`{name}`]({METHODS_PAGE})" if name in catalog_methods else f"`{name}`"

    active = [[f"`{p.name}`", _method(p.method)] for p in site.practices if not p.pending]
    pending = [p.name for p in site.practices if p.pending]
    blocks = [
        "## The techniques adapted here",
        f"A Practice is APS's facility-tuned form of a cross-facility [Method]({MODEL_PAGE}): the "
        "ISA-88 Site Recipe layer. The Method names a technique abstractly in the Catalog; the "
        "Practice is how 2-BM runs it here. Each row links up to the Method it adapts.",
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


def _principals(site: Site) -> list[str]:
    actor_active = [[a.name, f"`{a.kind}`"] for a in site.actors if not a.pending]
    actor_pending = [a.name for a in site.actors if a.pending]
    agent_rows = [
        [f"`{a.name}`", f"`{a.version}`", f"`{a.model_provider} / {a.model_name}`"]
        for a in site.agents
        if not a.pending
    ]
    blocks = [
        "## Who acts here",
        "Every action CORA records is attributed to a principal. At APS those are the people "
        "registered facility-wide (the operator on shift, safety reviewers, proposal PIs) and the "
        "autonomous agents. Human display names live in `actor_profile` (the editable, forgettable "
        "layer), not in the event-sourced Actor record, which carries only id and kind.",
        _table(["Person or service", "Kind"], actor_active),
    ]
    blocks += _planned(actor_pending)
    blocks += [
        "Agents are advisory LLM principals. Each one's id is shared with an Access Actor "
        "(`kind=agent`) through a single cross-BC atomic write, so an agent's writes attribute the "
        "same way a person's do. They observe and advise; they never gate Run state.",
        _table(["Agent", "Version", "Model"], agent_rows),
    ]
    return blocks


def _modeled() -> list[str]:
    return [
        "## How APS is modeled",
        "APS itself is not an Asset: it is a Federation `Facility` with `FacilityKind = Site`. The "
        "beamlines it hosts are the root Assets, each bound to the Site by `facility_code`; their "
        f"sub-systems nest below by `parent_id`. See [Assets](assets.md) for that binding and "
        f"[the CORA model]({MODEL_PAGE}) for the aggregate shapes.",
    ]


def render_all(site: Site, *, catalog_methods: frozenset[str] = frozenset()) -> dict[str, str]:
    blocks = ["# APS"]
    blocks += _facility(site)
    blocks += _techniques(site, catalog_methods)
    blocks += _resources(site)
    blocks += _safety(site)
    blocks += _principals(site)
    blocks += _modeled()
    return {"deployments/aps/index.md": "\n\n".join(blocks) + "\n"}
