"""Guards for the site descriptor (deployments/aps/site.yaml).

Four kinds of guard, matching the no-drift boundary:
  - round-trip: the descriptor loads and validates against its schema.
  - enum-equality: the closed-vocabulary frozensets mirrored in
    scripts/site_descriptor.py equal their cora enums (FacilityKind, ActorKind).
  - agent drift-guard: the two LLM agents authored in site.yaml (RunDebriefer +
    CautionDrafter) equal the code seeds, so a seeded agent missing from the docs
    (or a model / version / kind drift between code and docs) fails the build. The
    three deterministic agents are authored pending and surfaced as planned.
  - facility invariants: the facility records what the bootstrap actually seeds
    (kind=Site, display_name == code).

The scripts/ module is loaded via importlib (scripts/ is not on the
type-checker's path); the cora enums + seed constants are imported normally.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cora.access.aggregates.actor import ActorKind
from cora.agent.prompts.caution_drafter import DEFAULT_CAUTION_DRAFTER_MODEL
from cora.agent.prompts.run_debrief import DEFAULT_RUN_DEBRIEF_MODEL
from cora.agent.seed import (
    RUN_DEBRIEFER_AGENT_KIND,
    RUN_DEBRIEFER_AGENT_NAME,
    RUN_DEBRIEFER_AGENT_VERSION,
)
from cora.agent.seed_caution_drafter import (
    CAUTION_DRAFTER_AGENT_KIND,
    CAUTION_DRAFTER_AGENT_NAME,
    CAUTION_DRAFTER_AGENT_VERSION,
)
from cora.federation.aggregates.facility import FacilityKind

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_SITE = _REPO_ROOT / "deployments" / "aps" / "site.yaml"
_CATALOG = _REPO_ROOT / "catalog" / "catalog.yaml"
# Every site descriptor, so a new Site (e.g. MAX IV) is auto-enrolled in the
# generic load + facility-invariant guard below. The APS-specific agent-seed
# assertions stay pinned to _SITE.
_ALL_SITES = sorted((_REPO_ROOT / "deployments").glob("*/site.yaml"))

_VALID_FACILITY = "facility:\n  code: aps\n  display_name: aps\n  kind: Site\n"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sd = _load("site_descriptor")
sp = _load("site_pages")
cd = _load("catalog_descriptor")


@pytest.mark.parametrize("site_path", _ALL_SITES, ids=lambda p: p.parent.name)
def test_every_site_loads_and_holds_facility_invariants(site_path: Path) -> None:
    """Every deployments/<site>/site.yaml loads and records the bootstrap
    invariants the seeder relies on (kind=Site, display_name == code). This
    auto-enrolls new Sites so a malformed second-site descriptor fails the fast
    unit suite, not only the docs build."""
    site = sd.load(site_path)
    assert site.facility.kind == FacilityKind.SITE.value
    assert site.facility.display_name == site.facility.code


def test_site_loads_and_validates() -> None:
    site = sd.load(_SITE)
    assert site.facility.code == "aps"
    assert site.facility.kind == "Site"
    # lower bounds, not exact: additive edits should not break this test, except
    # agents which are drift-guarded against the code seeds below. The two
    # non-pending LLM agents are equality-checked in test_agents_match_seed_constants;
    # RunSupervisor + CautionPromoter + ClearanceExpirer + ClearanceWatcher are
    # authored pending (identity seeded, runtimes not yet operational).
    assert len(site.practices) >= 17
    assert len(site.actors) >= 9
    assert len(site.agents) == 6
    assert len(site.supplies) >= 1
    assert len(site.clearances) >= 1
    assert len(site.cautions) >= 1


def test_facility_kind_mirror_matches_code() -> None:
    assert {k.value for k in FacilityKind} == sd.FACILITY_KINDS


def test_actor_kind_mirror_matches_code() -> None:
    assert {k.value for k in ActorKind} == sd.ACTOR_KINDS


def test_agents_match_seed_constants() -> None:
    site = sd.load(_SITE)
    expected = {
        RUN_DEBRIEFER_AGENT_NAME: (
            RUN_DEBRIEFER_AGENT_KIND,
            RUN_DEBRIEFER_AGENT_VERSION,
            DEFAULT_RUN_DEBRIEF_MODEL.provider,
            DEFAULT_RUN_DEBRIEF_MODEL.model,
        ),
        CAUTION_DRAFTER_AGENT_NAME: (
            CAUTION_DRAFTER_AGENT_KIND,
            CAUTION_DRAFTER_AGENT_VERSION,
            DEFAULT_CAUTION_DRAFTER_MODEL.provider,
            DEFAULT_CAUTION_DRAFTER_MODEL.model,
        ),
    }
    actual = {
        a.name: (a.kind, a.version, a.model_provider, a.model_name)
        for a in site.agents
        if not a.pending
    }
    assert actual == expected


def test_facility_invariants_match_bootstrap() -> None:
    site = sd.load(_SITE)
    assert site.facility.kind == FacilityKind.SITE.value
    # bootstrap seeds display_name == code (federation/_bootstrap.py) until a
    # future rename slice; pin that invariant, not the env-derived code value.
    assert site.facility.display_name == site.facility.code


def test_site_guards_reject_bad_data(tmp_path: Path) -> None:
    unknown_actor_kind = tmp_path / "unknown_actor.yaml"
    unknown_actor_kind.write_text(
        _VALID_FACILITY + "actors:\n  - {name: X, kind: alien}\n",
        encoding="utf-8",
    )
    with pytest.raises(sd.SiteError):
        sd.load(unknown_actor_kind)

    unknown_facility_kind = tmp_path / "unknown_facility.yaml"
    unknown_facility_kind.write_text(
        "facility:\n  code: x\n  display_name: x\n  kind: Galaxy\n",
        encoding="utf-8",
    )
    with pytest.raises(sd.SiteError):
        sd.load(unknown_facility_kind)

    typo = tmp_path / "typo.yaml"
    typo.write_text(
        "facility:\n  code: x\n  display_name: x\n  kind: Site\n  kindd: oops\n",
        encoding="utf-8",
    )
    with pytest.raises(sd.SiteError):
        sd.load(typo)

    duplicate_practice = tmp_path / "dupe.yaml"
    duplicate_practice.write_text(
        _VALID_FACILITY + "practices:\n  - {name: p, method: m}\n  - {name: p, method: n}\n",
        encoding="utf-8",
    )
    with pytest.raises(sd.SiteError):
        sd.load(duplicate_practice)


def test_renders_single_site_narrative() -> None:
    site = sd.load(_SITE)
    pages = sp.render_all(site, catalog_methods=frozenset({"tomography", "dark_field"}))
    # one reader-first narrative, NOT one page per bounded context
    assert set(pages) == {"deployments/aps/index.md"}
    page = pages["deployments/aps/index.md"]
    assert page.startswith("# APS")
    assert chr(0x2014) not in page
    # organized by the reader's journey, not by aggregate
    for heading in (
        "## The techniques adapted here",
        "## The resources you draw on",
        "## The safety envelope",
        "## Who acts here",
    ):
        assert heading in page, f"missing section {heading}"
    # both active agents surfaced with their models (the gap-fix)
    assert "CautionDrafter" in page and "claude-sonnet-4-6" in page
    assert "RunDebriefer" in page and "claude-haiku-4-5" in page
    # the three deterministic agents are seeded pending; surface them so all five
    # are discoverable on the deployment page, not just the two live LLM ones
    for pending_agent in ("RunSupervisor", "CautionPromoter", "ClearanceExpirer"):
        assert pending_agent in page, f"pending agent {pending_agent} not surfaced"
    # content woven in from every folded list
    assert "[`tomography`](../../catalog/methods.md)" in page  # practice -> catalog method
    assert "`human`" in page  # principals
    assert "LiquidHelium" in page  # supplies
    assert "ESAF" in page  # clearances
    assert "beam-flux transients" in page  # cautions
    assert "Institution" in page and "Argonne" in page  # facility -> institution (context)
    assert "../argonne/index.md" not in page  # institution is context, not a navigable deployment
    # the Asset binding is dissolved into this page, not a separate Assets sub-page
    assert "## How APS is modeled" in page
    assert "../2-bm/index.md" in page  # beamline root Asset binding, folded in
    assert "`Unit`" in page  # asset tier column rendered inline
    assert "assets.md" not in page  # no link-out to a hand-authored Assets page


def test_practice_method_links_only_known() -> None:
    site = sd.load(_SITE)
    page = sp.render_all(site, catalog_methods=frozenset({"tomography"}))[
        "deployments/aps/index.md"
    ]
    # known catalog method renders as a link
    assert "[`tomography`](../../catalog/methods.md)" in page
    # a method not in the catalog renders unlinked (bare code span)
    assert "`hexapod_reboot`" in page
    assert "[`hexapod_reboot`]" not in page


# ---------------------------------------------------------------------------
# Methods-axis guards: practice (ISA-88 Site Recipe) -> catalog Method.
#
# A practice names a catalog Method. If the Method exists it renders as a link;
# if not, the practice marks it pending: true and it renders unlinked until the
# Method graduates into the catalog. The site loader never sees the catalog, so a
# typo'd method name is otherwise indistinguishable from a deliberate pending
# method. These two guards close that, the methods-axis analog of the family
# guards in test_beamline_descriptor.py:
#   - a non-pending practice method must resolve in the catalog;
#   - a pending method must be a deliberate, reasoned registry entry.
# The >=2-deployment promotion SIGNAL (the family-promotion analog) is not added
# yet: methods are staged per-site, so a method's beamline spread is not
# structurally measurable today (it lives only in the practice-name prefix), and
# no pending method spans two sites. _PENDING_METHODS is the registry a future
# signal would read once practices carry a typed beamline.
# ---------------------------------------------------------------------------

_PENDING_METHODS = {
    "energy_dispersive_diffraction": "7-BM white-beam EDD; not yet in pilot scope (TECH-1)",
    "high_speed_imaging": "7-BM chopper-gated movie bursts; not yet in pilot scope (TECH-1)",
    "radiography": "7-BM time-resolved point radiography; not yet in scope (TECH-1)",
    "first_light": "19-BM-FACT commissioning method; design phase",
    "ioc_restart": "2-BM maintenance recovery; portable Method not yet authored",
    "mirror_recoat_return": "2-BM mirror recoat-and-return; Method not yet authored",
    "scanning_fluorescence_microscopy": "2-ID scanning XRF microprobe; Method not yet earned",
    "diffraction": "4-ID POLAR single-crystal diffraction; not yet in pilot scope (TECH-1)",
    "magnetic_scattering": "4-ID POLAR magnetic scattering; not yet in pilot scope (TECH-1)",
    "resonant_scattering": "4-ID POLAR resonant scattering; not yet in pilot scope (TECH-1)",
    "xmcd": "4-ID POLAR magnetic circular dichroism; not yet in pilot scope (TECH-1)",
    "xpcs": "8-ID photon correlation spectroscopy; not yet in pilot scope (TECH-1)",
    "grid_scan": "i03 MX fast grid scan; portable Method not yet earned",
    "mx_data_collection": "i03 MX rotation data collection; Method not yet earned",
    "sample_exchange": "i03 autonomous robotic sample exchange; Method not yet earned",
    "small_angle_scattering": "i22 + 8-ID SAXS; portable Method not yet earned",
    "wide_angle_scattering": "i22 WAXS; portable Method not yet earned",
    "total_scattering": "i15-1 total scattering / PDF; Method not yet earned",
    "powder_diffraction": "i11 powder diffraction; portable Method not yet earned",
}


def _catalog_method_names() -> set[str]:
    return {m.name for m in cd.load(_CATALOG).methods}


def _pending_practice_methods() -> set[str]:
    catalog_methods = _catalog_method_names()
    return {
        practice.method
        for site_path in _ALL_SITES
        for practice in sd.load(site_path).practices
        if practice.pending and practice.method not in catalog_methods
    }


@pytest.mark.parametrize("site_path", _ALL_SITES, ids=lambda p: p.parent.name)
def test_nonpending_practice_methods_resolve_in_catalog(site_path: Path) -> None:
    catalog_methods = _catalog_method_names()
    site = sd.load(site_path)
    dangling = sorted(
        f"{practice.name} -> {practice.method}"
        for practice in site.practices
        if not practice.pending and practice.method not in catalog_methods
    )
    assert not dangling, (
        f"{site_path.parent.name}: non-pending practices name a method absent from the "
        f"catalog (a typo, or a method that should be marked pending: true): {dangling}"
    )


def test_pending_practice_methods_are_registered() -> None:
    pending = _pending_practice_methods()
    unexpected = sorted(pending - set(_PENDING_METHODS))
    assert not unexpected, (
        "site practices mark methods pending: that are not registered (a typo, or a newly "
        "staged technique); add to _PENDING_METHODS with a reason or graduate into the "
        f"catalog: {unexpected}"
    )
    stale = sorted(set(_PENDING_METHODS) - pending)
    assert not stale, (
        "registered pending methods no longer named by any pending practice (graduated into "
        f"the catalog or removed); drop from _PENDING_METHODS: {stale}"
    )


def test_malformed_site_raises(tmp_path: Path) -> None:
    not_a_mapping = tmp_path / "list.yaml"
    not_a_mapping.write_text("- just a list\n", encoding="utf-8")
    with pytest.raises(sd.SiteError):
        sd.load(not_a_mapping)

    missing_facility = tmp_path / "no_facility.yaml"
    missing_facility.write_text("practices: []\n", encoding="utf-8")
    with pytest.raises(sd.SiteError):
        sd.load(missing_facility)

    practice_missing_method = tmp_path / "bad_practice.yaml"
    practice_missing_method.write_text(
        _VALID_FACILITY + "practices:\n  - {name: p}\n",
        encoding="utf-8",
    )
    with pytest.raises(sd.SiteError):
        sd.load(practice_missing_method)
