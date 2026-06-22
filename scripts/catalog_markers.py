"""Expand `catalog:*` markers on deployment pages from the catalog descriptor.

A deployment page often shows a curated subset of the cross-facility catalog: the
vendor Models its hardware binds. Hand-retyping the manufacturer and part number
is a drift surface (a wrong part number is exactly the kind of fact staff notice),
so those cells are rendered from catalog/catalog.yaml via a paired marker:

    <!-- catalog:models models=flir_oryx,crytur_luag show=families -->
    ...regenerable table the build overwrites...
    <!-- /catalog:models -->

`models` is the ordered, comma-separated set of Model names to show (each must
exist in the catalog, so a typo or a renamed Model fails the build). `show`
picks the fourth column: `families` (the Model's declared Families, from the
catalog) or `usedby` (the deployment's Assets that bind the Model, derived from
the beamline descriptor). Manufacturer and part number always come from the
catalog.

This is the catalog-tier counterpart of scripts/beamline_markers.py; the
on_page_markdown hook in scripts/mkdocs_hooks.py calls `expand_markers` for every
deployments/ page carrying a catalog:* marker. A malformed, unknown, unpaired, or
empty-rendering marker raises CatalogMarkerError and aborts the build.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from beamline_descriptor import BeamlineDescriptor, Device
    from catalog_descriptor import Catalog

_SHOW_KINDS = frozenset({"families", "usedby"})

REPO_BLOB = "https://github.com/xmap/cora/blob/main/"
_CATALOG_URL = f"{REPO_BLOB}catalog/catalog.yaml"
_SOURCE_NOTE = (
    '!!! info "Generated from the catalog"\n'
    f"    This table is generated from [`catalog/catalog.yaml`]({_CATALOG_URL}). "
    "Edit the catalog, not this table."
)


class CatalogMarkerError(ValueError):
    """A catalog marker is malformed, unknown, or renders empty."""


def _esc(text: str) -> str:
    return text.replace("|", r"\|")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_esc(c) if c else "" for c in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _codes(names: list[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


def _all_devices(descriptor: BeamlineDescriptor) -> list[Device]:
    """Every device in the descriptor: beam-path groups (with nested
    constituents) plus the cross-cutting controllers and trigger boxes."""
    devices: list[Device] = []

    def _walk(items: list[Device] | None) -> None:
        for device in items or []:
            devices.append(device)
            _walk(device.constituents)

    for _key, group in descriptor.groups:
        _walk(group.devices)
    if descriptor.controls is not None:
        _walk(descriptor.controls.motion_controllers)
        _walk(descriptor.controls.triggering)
    return devices


def _used_by(descriptor: BeamlineDescriptor | None, model_name: str) -> str:
    if descriptor is None:
        return ""
    return _codes([d.name for d in _all_devices(descriptor) if d.model == model_name])


def render_models(
    catalog: Catalog, descriptor: BeamlineDescriptor | None, args: dict[str, str]
) -> str:
    """A vendor-catalog table for an explicit, ordered set of Models."""
    show = args.get("show", "families")
    if show not in _SHOW_KINDS:
        raise CatalogMarkerError(
            f"catalog:models: unknown show {show!r}; expected one of {sorted(_SHOW_KINDS)}"
        )
    names = [name for name in args["models"].split(",") if name]
    if not names:
        raise CatalogMarkerError("catalog:models: empty models list")

    by_name = {m.name: m for m in catalog.models}
    rows: list[list[str]] = []
    for name in names:
        model = by_name.get(name)
        if model is None:
            raise CatalogMarkerError(f"catalog:models: unknown Model {name!r} (not in catalog)")
        last = _codes(model.declared_families) if show == "families" else _used_by(descriptor, name)
        rows.append(
            [
                f"`{model.name}`",
                model.manufacturer.name,
                f"`{model.part_number}`",
                last,
            ]
        )
    header = "Declared families" if show == "families" else "Used by"
    return _table(["Model", "Manufacturer", "Part number", header], rows)


RENDERERS = {
    "models": render_models,
}
REQUIRED_ARGS: dict[str, frozenset[str]] = {
    "models": frozenset({"models"}),
}
OPTIONAL_ARGS: dict[str, frozenset[str]] = {
    "models": frozenset({"show"}),
}

_MARKER_RE = re.compile(
    r"<!--\s*catalog:(?P<kind>[a-z][a-z0-9-]*)(?P<args>(?:\s+[a-z_]+=[^\s>]+)*)\s*-->"
    r"(?P<body>.*?)"
    r"<!--\s*/catalog:(?P=kind)\s*-->",
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
        raise CatalogMarkerError(f"{src_uri}: catalog:{kind} has unknown args {sorted(unknown)}")
    missing = REQUIRED_ARGS[kind] - set(args)
    if missing:
        raise CatalogMarkerError(f"{src_uri}: catalog:{kind} missing required args {sorted(missing)}")
    return args


def expand_markers(
    markdown: str,
    *,
    catalog: Catalog,
    descriptor: BeamlineDescriptor | None,
    src_uri: str,
) -> str:
    """Replace every `catalog:*` marker body with a table rendered from the
    catalog (and, for the used-by column, the beamline descriptor). Raises
    CatalogMarkerError on any malformed, unknown, unpaired, or empty-rendering
    marker so the build fails loudly."""
    matched = 0

    def _repl(m: re.Match[str]) -> str:
        nonlocal matched
        matched += 1
        kind = m.group("kind")
        if kind not in RENDERERS:
            raise CatalogMarkerError(f"{src_uri}: unknown catalog marker kind {kind!r}")
        args = _parse_args(kind, m.group("args"), src_uri)
        body = RENDERERS[kind](catalog, descriptor, args)
        if not body:
            raise CatalogMarkerError(f"{src_uri}: catalog:{kind} rendered empty")
        open_marker = f"<!-- catalog:{kind}{m.group('args')} -->"
        close_marker = f"<!-- /catalog:{kind} -->"
        return f"{open_marker}\n{_SOURCE_NOTE}\n\n{body}\n{close_marker}"

    out = _MARKER_RE.sub(_repl, markdown)
    opens = len(re.findall(r"<!--\s*catalog:", markdown))
    closes = len(re.findall(r"<!--\s*/catalog:", markdown))
    if opens != matched or closes != matched:
        raise CatalogMarkerError(
            f"{src_uri}: malformed or unpaired catalog marker "
            f"(open={opens}, close={closes}, matched={matched})"
        )
    return out
