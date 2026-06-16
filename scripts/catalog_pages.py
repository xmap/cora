"""Render the catalog descriptor into the Catalog inventory pages.

`render_all(catalog)` returns a {src_uri: markdown} dict with one generated page
per kind: capabilities, methods, families, roles, models, assemblies. Each page
is the clean fact table plus per-item one-liners from the descriptor, and links
up to the hand-authored Catalog hub (catalog/index.md) for the naming /
governance / closed-core conventions.

The mkdocs on_files hook in scripts/mkdocs_hooks.py injects these as virtual
files at build time; nothing is written to disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from catalog_descriptor import Catalog

CATALOG_BLOB_URL = "https://github.com/xmap/cora/blob/main/catalog/catalog.yaml"


def _esc(text: str) -> str:
    return text.replace("|", r"\|")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_esc(cell) if cell else "" for cell in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _banner() -> str:
    return (
        '!!! info "Generated from the catalog descriptor"\n'
        f"    This page is generated from [`catalog/catalog.yaml`]({CATALOG_BLOB_URL}). "
        "Edit the descriptor, not this page. For the naming, governance, and "
        "closed-core conventions, see [the Catalog overview](index.md)."
    )


def _codes(values: list[str]) -> str:
    return ", ".join(f"`{v}`" for v in values)


def _capabilities(catalog: Catalog) -> str:
    binds: dict[str, list[str]] = {}
    for m in catalog.methods:
        if m.capability:
            binds.setdefault(m.capability, []).append(m.name)
    rows = [
        [
            f"`{c.code}`",
            c.name,
            _codes(sorted(binds.get(c.code, []))),
            c.description or "",
        ]
        for c in catalog.capabilities
    ]
    return "\n\n".join(
        [
            "# Capabilities",
            "The operations-layer templates that declare what an operation provides. "
            "Each Method binds to one Capability.",
            _banner(),
            _table(["Code", "Name", "Binds methods", "Description"], rows),
        ]
    )


def _methods(catalog: Catalog) -> str:
    rows = [
        [
            f"`{m.name}`",
            f"[`{m.capability}`](capabilities.md)" if m.capability else "",
            _codes(m.needed_families),
            m.purpose or "",
        ]
        for m in catalog.methods
    ]
    return "\n\n".join(
        [
            "# Methods",
            "The technique catalog. Each Method names a technique abstractly and "
            "declares the device [Families](families.md) it needs and the "
            "[Capability](capabilities.md) contract it realizes.",
            _banner(),
            _table(["Method", "Capability", "Needed families", "Purpose"], rows),
        ]
    )


def _families(catalog: Catalog) -> str:
    used_by: dict[str, list[str]] = {}
    for m in catalog.methods:
        for fam in m.needed_families:
            used_by.setdefault(fam, []).append(m.name)
    rows = [
        [
            f"`{f.name}`",
            _codes(sorted(used_by.get(f.name, []))),
            f.note or "",
        ]
        for f in catalog.families
    ]
    return "\n\n".join(
        [
            "# Families",
            "The device-class abstractions a Method declares as `needed_families`. "
            "Affordances are a Role concern, so they live on [Roles](roles.md), not "
            "here; a Family advertises which Roles it satisfies via `presents_as`.",
            _banner(),
            _table(["Family", "Used by methods", "Note"], rows),
        ]
    )


def _roles(catalog: Catalog) -> str:
    rows = [
        [
            f"`{r.name}`",
            _codes(r.required_affordances),
            _codes(r.optional_affordances),
            r.docstring,
        ]
        for r in catalog.roles
    ]
    return "\n\n".join(
        [
            "# Roles",
            "The functional binding contracts a Method references via "
            "`required_roles`. A Family or Assembly advertises which Roles it "
            "satisfies via `presents_as`. Affordance names are the closed primitive "
            "set; see [Affordances](../reference/affordances.md).",
            _banner(),
            _table(
                ["Role", "Required affordances", "Optional affordances", "Contract"],
                rows,
            ),
        ]
    )


def _models(catalog: Catalog) -> str:
    rows = [
        [
            f"`{m.name}`",
            m.manufacturer.name,
            f"`{m.part_number}`",
            _codes(m.declared_families),
        ]
        for m in catalog.models
    ]
    return "\n\n".join(
        [
            "# Models",
            "The vendor product catalog. A Model carries manufacturer identity and "
            "the Families it satisfies; a beamline Asset binds a Model to record "
            "what specific hardware it is. The per-deployment binding lives on the "
            "beamline page, not here.",
            _banner(),
            _table(["Model", "Manufacturer", "Part number", "Declared families"], rows),
        ]
    )


def _assemblies(catalog: Catalog) -> str:
    rows = [
        [
            f"`{a.name}`",
            _codes(a.presents_as),
            "; ".join(
                f"`{s.slot_name}` ({s.cardinality}): {_codes(s.required_families)}"
                + (f" (defaults: {_codes(sorted(s.default_settings))})" if s.default_settings else "")
                + (" (default placement)" if s.default_placement else "")
                for s in a.required_slots
            ),
            ", ".join(
                f"`{link.slot_name}` -> `{link.sub_assembly}`"
                for link in a.required_sub_assemblies
            ),
            a.note or "",
        ]
        for a in catalog.assemblies
    ]
    return "\n\n".join(
        [
            "# Assemblies",
            "Reusable composition blueprints: a named cluster of Family-typed slots "
            "(cardinality-annotated), optional slot-to-slot wires, and version-pinned "
            "sub-assembly links to child blueprints. An Assembly advertises which "
            "[Roles](roles.md) it satisfies via `presents_as`, at the same level a single "
            "Asset does. A beamline materializes a blueprint into specific hardware as a "
            "Fixture; that per-deployment binding lives on the beamline page, not here. The "
            "running system assigns each Assembly a content-hash identity, so two facilities "
            "that publish the same blueprint converge; this page is the human vocabulary, "
            "keyed by name.",
            _banner(),
            _table(["Assembly", "Presents as", "Slots", "Sub-assemblies", "Note"], rows),
        ]
    )


def render_all(catalog: Catalog) -> dict[str, str]:
    return {
        "catalog/capabilities.md": _capabilities(catalog) + "\n",
        "catalog/methods.md": _methods(catalog) + "\n",
        "catalog/families.md": _families(catalog) + "\n",
        "catalog/assemblies.md": _assemblies(catalog) + "\n",
        "catalog/roles.md": _roles(catalog) + "\n",
        "catalog/models.md": _models(catalog) + "\n",
    }
