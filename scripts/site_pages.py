"""Render the site descriptor into the APS site pages.

`render_all(site, catalog_methods=...)` returns a {src_uri: markdown} dict with
one generated page per site surface: the Facility landing (index.md), Practices,
Actors, and Agents. Each page is the clean fact table plus per-item one-liners
from the descriptor.

A Practice method renders as a link to the generated Catalog Methods page only
when the method is present in the catalog (threaded in as `catalog_methods`);
methods still pending in the catalog render unlinked, exactly as the prior
hand-authored page did.

The mkdocs on_files hook in scripts/mkdocs_hooks.py injects these as virtual
files at build time; nothing is written to disk.
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


def _facility(site: Site) -> str:
    f = site.facility
    rows = [
        ["Facility code", f"`{f.code}`"],
        ["Kind", f"`{f.kind}`"],
    ]
    if f.institution:
        rows.append(["Institution", f"[{f.institution}](../argonne/index.md)"])
    if f.sectors:
        rows.append(["Sectors under this Site", ", ".join(f"`{s}`" for s in f.sectors)])
    if f.beamlines:
        links = ", ".join(f"[{b}](../2-bm/index.md)" for b in f.beamlines)
        rows.append(["Beamlines under this Site", links])
    inventories = "\n".join(
        f"- [{label}]({target})"
        for label, target in (
            ("Assets", "assets.md"),
            ("Actors", "actors.md"),
            ("Agents", "agents.md"),
            ("Practices", "practices.md"),
            ("Clearances", "clearances.md"),
            ("Supplies", "supplies.md"),
            ("Cautions", "cautions.md"),
        )
    )
    return "\n\n".join(
        [
            "# APS",
            "Site-level inventories for APS: the Facility, the Practices registered here, the "
            "facility principals, and the facility-wide Clearances, Supplies, and Cautions.",
            _banner(),
            _table(["Property", "Value"], rows),
            "## Inventories",
            inventories,
        ]
    )


def _practices(site: Site, catalog_methods: frozenset[str]) -> str:
    def _method(name: str) -> str:
        return f"[`{name}`]({METHODS_PAGE})" if name in catalog_methods else f"`{name}`"

    active = [[f"`{p.name}`", _method(p.method)] for p in site.practices if not p.pending]
    pending = [
        [p.name, _method(p.method) + (f" ({p.note})" if p.note else "")]
        for p in site.practices
        if p.pending
    ]
    sections = [
        "# Practices",
        f"A Practice is ISA-88's Site Recipe, the facility-adapted form of a "
        f"[Method]({MODEL_PAGE}). Each Practice registered at APS binds one catalog Method.",
        _banner(),
        _table(["Practice", "Method"], active),
    ]
    if pending:
        sections += ["## Pending", _table(["Practice", "Method"], pending)]
    return "\n\n".join(sections)


def _actors(site: Site) -> str:
    active = [[a.name, f"`{a.kind}`"] for a in site.actors if not a.pending]
    pending = [
        [a.name + (f" ({a.note})" if a.note else ""), f"`{a.kind}`"]
        for a in site.actors
        if a.pending
    ]
    sections = [
        "# Actors",
        "Access BC Actors that are conceptually facility-wide at APS: User Office accounts "
        "(proposal PIs), safety-process reviewers, the canonical APS Operator identity, and each "
        "AI Agent's co-registered Actor row. Beamline-bound staff (the 2-BM operator pool) live "
        f"with their beamline. Actor display names live in `actor_profile`, not in event-sourced "
        f"Actor state. See [Model]({MODEL_PAGE}) for the aggregate shape.",
        _banner(),
        _table(["Actor", "Kind"], active),
    ]
    if pending:
        sections += ["## Pending", _table(["Actor", "Kind"], pending)]
    return "\n\n".join(sections)


def _agents(site: Site) -> str:
    rows = [
        [f"`{a.name}`", f"`{a.kind}`", f"`{a.version}`", f"`{a.model_provider} / {a.model_name}`"]
        for a in site.agents
        if not a.pending
    ]
    return "\n\n".join(
        [
            "# Agents",
            "Agent BC Agents seeded at this deployment. Each Agent's id is shared with an "
            "Access BC Actor (`kind=agent`) via a cross-BC atomic write (`ActorRegistered` + "
            "`AgentDefined` in one transaction). "
            f"See [Model]({MODEL_PAGE}) for the aggregate shape.",
            _banner(),
            _table(["Agent", "Kind", "Version", "Model"], rows),
        ]
    )


def render_all(site: Site, *, catalog_methods: frozenset[str] = frozenset()) -> dict[str, str]:
    return {
        "deployments/aps/index.md": _facility(site) + "\n",
        "deployments/aps/practices.md": _practices(site, catalog_methods) + "\n",
        "deployments/aps/actors.md": _actors(site) + "\n",
        "deployments/aps/agents.md": _agents(site) + "\n",
    }
