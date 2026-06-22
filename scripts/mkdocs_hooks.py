"""MkDocs build-time hooks.

Two distinct responsibilities (both registered in mkdocs.yml under `hooks:`):

A) **Link rewriting** (`on_page_markdown`). Rewrites markdown links
   in-memory so the static site at xmap.github.io/cora/ resolves
   correctly without mutating the source files in docs/.

   1. The staged reference/contributing.md (mirrored from /CONTRIBUTING.md
      at build time) has paths that are repo-root-relative. They are
      rewritten to either an intra-site mkdocs path (when the target is a
      docs/ page) or a GitHub blob URL (when the target is a repo file
      outside docs/).

   2. Every other page in docs/ is page-aware: links that resolve inside
      docs/ are left alone (mkdocs handles relative intra-site links
      natively); links that resolve outside docs/ are rewritten to GitHub
      blob URLs (or to the staged contributing page for the
      ../CONTRIBUTING.md special case).

   Links containing /.claude/ (private auto-memory) are stripped to plain
   text.

   It also expands `arch:*` markers on architecture/ pages: their bodies
   (the BC table, aggregate lists, counts, slice tables, FSM states) are
   rendered from the live cora code model (scripts/architecture_*), so the
   factual tables cannot drift. A malformed marker aborts the build.

B) **Generated pages** (`on_files`). Renders virtual pages from the
   descriptors: one beamline layout page per deployments/<id>/beamline.yaml
   (scripts/beamline_*), the Catalog inventory pages from catalog/catalog.yaml
   (scripts/catalog_*), and one site page per deployments/<site>/site.yaml
   (scripts/site_*). Deployments and sites are discovered by glob, so a new
   deployment renders without editing this hook. A missing or invalid
   descriptor raises and fails the build (mkdocs build --strict).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

REPO_BLOB = "https://github.com/xmap/cora/blob/main/"
HOOK_DIR = Path(__file__).resolve().parent
REPO_ROOT = HOOK_DIR.parent
DOCS_DIR = REPO_ROOT / "docs"
STAGED_CONTRIBUTING_SRC_URI = "reference/contributing.md"
DEPLOYMENTS_DIR = REPO_ROOT / "deployments"
CATALOG_PATH = REPO_ROOT / "catalog" / "catalog.yaml"
CORA_SRC = REPO_ROOT / "apps" / "api" / "src" / "cora"

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# Cached architecture model: introspecting the cora source is the same for every
# architecture/ page, so build it once per process.
_ARCH_MODEL: object | None = None

# Cached beamline descriptors, one per deployment id, so a deployment's pages
# share a single parsed descriptor across the build.
_BEAMLINE_DESCRIPTORS: dict[str, object] = {}

# Cached catalog descriptor: the cross-facility vocabulary is the same for every
# page, so parse catalog/catalog.yaml once per process.
_CATALOG: object | None = None


def _arch_model() -> object:
    global _ARCH_MODEL
    if _ARCH_MODEL is None:
        import architecture_introspect

        _ARCH_MODEL = architecture_introspect.introspect(CORA_SRC)
    return _ARCH_MODEL


def _beamline_descriptor_for(src_uri: str) -> object:
    """Load (and cache) the beamline descriptor for the deployment owning a page.

    `src_uri` is deployments/<id>/...; the descriptor is read from
    deployments/<id>/beamline.yaml. A missing or invalid descriptor raises and
    fails the build, so a beamline:* marker can never expand from stale data.
    """
    deployment_id = Path(src_uri).parts[1]
    if deployment_id not in _BEAMLINE_DESCRIPTORS:
        import beamline_descriptor

        path = DEPLOYMENTS_DIR / deployment_id / "beamline.yaml"
        _BEAMLINE_DESCRIPTORS[deployment_id] = beamline_descriptor.load(path)
    return _BEAMLINE_DESCRIPTORS[deployment_id]


def _catalog() -> object:
    global _CATALOG
    if _CATALOG is None:
        import catalog_descriptor

        _CATALOG = catalog_descriptor.load(CATALOG_PATH)
    return _CATALOG


# Ensure sibling scripts (beamline_descriptor, beamline_pages) are importable
# when mkdocs runs this hook with the repo root not on sys.path.
if str(HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(HOOK_DIR))


def _rewrite_in_page(page_src_uri: str, markdown: str) -> str:
    is_staged = page_src_uri == STAGED_CONTRIBUTING_SRC_URI
    page_path_in_docs = Path(page_src_uri)
    page_dir_in_docs = page_path_in_docs.parent
    # Number of "../" steps to climb from the page back to docs/ root.
    depth_to_docs_root = 0 if str(page_dir_in_docs) == "." else len(page_dir_in_docs.parts)
    up_to_docs_root = "../" * depth_to_docs_root

    def _rewrite(match: re.Match[str]) -> str:
        original = match.group(0)
        label, target = match.group(1), match.group(2)

        # Leave external links, anchors, and mailto alone.
        if target.startswith(("http://", "https://", "#", "mailto:")):
            return original

        # Strip links into private auto-memory.
        if "/.claude/" in target:
            return label

        # Split off any anchor fragment.
        if "#" in target:
            path_part, anchor = target.split("#", 1)
            anchor = "#" + anchor
        else:
            path_part, anchor = target, ""

        if not path_part:
            return original

        if is_staged:
            # Staged reference/contributing.md mirrors /CONTRIBUTING.md, so
            # paths in the source are repo-root-relative. Rewrite them to be
            # relative to the staged page's location (docs/reference/).
            cleaned = path_part
            while cleaned.startswith("../"):
                cleaned = cleaned[3:]
            while cleaned.startswith("./"):
                cleaned = cleaned[2:]

            if cleaned == "CONTRIBUTING.md":
                return f"[{label}](contributing.md{anchor})"
            if cleaned.startswith("docs/"):
                cleaned = cleaned[len("docs/") :]
                if cleaned == "" or cleaned.endswith("/"):
                    return f"[{label}]({up_to_docs_root}index.md{anchor})"
                return f"[{label}]({up_to_docs_root}{cleaned}{anchor})"

            return f"[{label}]({REPO_BLOB}{cleaned}{anchor})"

        # Non-staged page in docs/: paths are page-relative mkdocs links.
        # Resolve to determine whether the target lives in docs/.
        page_dir_abs = (DOCS_DIR / page_dir_in_docs).resolve()
        try:
            resolved = (page_dir_abs / path_part).resolve()
        except (OSError, RuntimeError):
            return original

        # Inside docs/ -> mkdocs handles natively, leave alone.
        try:
            resolved.relative_to(DOCS_DIR.resolve())
            return original
        except ValueError:
            pass

        # Outside docs/ but inside the repo: rewrite.
        try:
            rel_in_repo = resolved.relative_to(REPO_ROOT.resolve()).as_posix()
        except ValueError:
            return original

        if rel_in_repo == "CONTRIBUTING.md":
            return f"[{label}]({up_to_docs_root}reference/contributing.md{anchor})"

        return f"[{label}]({REPO_BLOB}{rel_in_repo}{anchor})"

    return LINK_RE.sub(_rewrite, markdown)


def on_page_markdown(
    markdown: str,
    *,
    page: Any,
    config: Any,
    files: Any,
) -> str:
    src_uri = page.file.src_uri
    # Architecture pages carry arch:* markers whose bodies are rendered from the
    # live code model (expand before link-rewrite so generated links resolve too).
    if src_uri.startswith("architecture/") and "<!-- arch:" in markdown:
        import architecture_pages

        markdown = architecture_pages.expand_markers(markdown, model=_arch_model(), src_uri=src_uri)
    # Deployment pages carry beamline:* markers whose tables are rendered from the
    # deployment's beamline descriptor (expand before link-rewrite).
    if src_uri.startswith("deployments/") and "<!-- beamline:" in markdown:
        import beamline_markers

        markdown = beamline_markers.expand_markers(
            markdown, descriptor=_beamline_descriptor_for(src_uri), src_uri=src_uri
        )
    # Deployment pages also carry catalog:* markers whose vendor-Model tables are
    # rendered from the catalog (plus the descriptor for the used-by column).
    if src_uri.startswith("deployments/") and "<!-- catalog:" in markdown:
        import catalog_markers

        markdown = catalog_markers.expand_markers(
            markdown,
            catalog=_catalog(),
            descriptor=_beamline_descriptor_for(src_uri),
            src_uri=src_uri,
        )
    return _rewrite_in_page(src_uri, markdown)


def on_files(files: Any, *, config: Any) -> Any:
    """Inject the generated pages as virtual files.

    Renders one beamline layout page per deployments/<id>/beamline.yaml, the
    Catalog inventory pages, and one site page per deployments/<site>/site.yaml.
    Both are discovered by glob (slug = the folder name). A missing or invalid
    descriptor raises and fails the build.
    """
    # Defensive: re-assert the sys.path entry inside the function. The
    # module-scope insert can be lost depending on how mkdocs loads hooks.
    if str(HOOK_DIR) not in sys.path:
        sys.path.insert(0, str(HOOK_DIR))

    import beamline_descriptor
    import beamline_pages
    import catalog_descriptor
    import catalog_pages
    import site_descriptor
    import site_pages
    from mkdocs.structure.files import File

    catalog = catalog_descriptor.load(CATALOG_PATH)
    catalog_families = frozenset(f.name for f in catalog.families)
    catalog_models = frozenset(m.name for m in catalog.models)
    catalog_methods = frozenset(m.name for m in catalog.methods)

    generated: dict[str, str] = {}

    # Beamlines: render each, and build the facility -> [(label, slug)] map the
    # site pages use to cross-link to the beamlines they actually host.
    beamlines_by_site: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(DEPLOYMENTS_DIR.glob("*/beamline.yaml")):
        slug = path.parent.name
        descriptor = beamline_descriptor.load(path)
        generated.update(
            beamline_pages.render_all(
                descriptor,
                slug=slug,
                catalog_families=catalog_families,
                catalog_models=catalog_models,
            )
        )
        facility = descriptor.beamline.facility
        if facility:
            label = descriptor.beamline.name or slug
            beamlines_by_site.setdefault(facility, []).append((label, slug))

    generated.update(catalog_pages.render_all(catalog))

    for path in sorted(DEPLOYMENTS_DIR.glob("*/site.yaml")):
        slug = path.parent.name
        site = site_descriptor.load(path)
        generated.update(
            site_pages.render_all(
                site,
                slug=slug,
                catalog_methods=catalog_methods,
                beamlines=beamlines_by_site.get(site.facility.code, []),
            )
        )

    for src_uri, content in generated.items():
        files.append(File.generated(config, src_uri, content=content))
    return files
