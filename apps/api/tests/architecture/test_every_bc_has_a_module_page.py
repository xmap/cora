"""Every shipping BC has a module page, and that page is reachable.

The architecture Model page renders a generated BC table whose status
legend promises "Active = aggregate is shipping and listed under
Modules". Nothing enforced the second half. Budget shipped its
Allocation aggregate on 2026-07-13 and went straight into the table as
Active while `/architecture/modules/budget/` returned 404: no page, no
nav entry, no card. The site broke its own stated promise for four
weeks and every check stayed green.

Three things have to move together for a BC to be readable, so all
three are asserted here: the page file exists, mkdocs nav points at it,
and the Modules landing grid carries a card linking to it. A BC that
ships without docs now fails here instead of on the published site.
"""

from __future__ import annotations

import re

from .conftest import BCS, CORA_ROOT

_REPO_ROOT = CORA_ROOT.parents[3]
_MODULES_DIR = _REPO_ROOT / "docs" / "architecture" / "modules"
_MODULES_INDEX = _MODULES_DIR / "index.md"
_MKDOCS_YML = _REPO_ROOT / "mkdocs.yml"


def test_every_bc_has_a_module_page() -> None:
    missing = [bc for bc in BCS if not (_MODULES_DIR / bc / "index.md").is_file()]
    assert not missing, (
        f"BCs with no docs/architecture/modules/<bc>/index.md: {missing}. "
        f"The Model page's status legend promises every Active BC is listed under Modules."
    )


def test_every_module_page_is_in_the_mkdocs_nav() -> None:
    nav = _MKDOCS_YML.read_text(encoding="utf-8")
    missing = [bc for bc in BCS if f"architecture/modules/{bc}/index.md" not in nav]
    assert not missing, f"module pages absent from the mkdocs nav: {missing}"


def test_every_module_page_has_a_landing_card() -> None:
    index = _MODULES_INDEX.read_text(encoding="utf-8")
    linked = set(re.findall(r"\]\((\w+)/index\.md\)", index))
    missing = sorted(set(BCS) - linked)
    assert not missing, f"BCs with no card on the Modules landing grid: {missing}"


def test_no_module_page_without_a_bc() -> None:
    # The inverse drift: a page left behind by a renamed or removed BC.
    pages = {p.name for p in _MODULES_DIR.iterdir() if p.is_dir()}
    orphans = sorted(pages - set(BCS))
    assert not orphans, f"module pages with no matching BC: {orphans}"
