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
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
bd = _load("beamline_descriptor")


@pytest.mark.parametrize("site_path", _ALL_SITES, ids=lambda p: p.parent.name)
def test_every_site_loads_and_holds_facility_invariants(site_path: Path) -> None:
    """Every deployments/<site>/site.yaml loads and records the bootstrap
    invariants the seeder relies on (kind=Site, display_name == code). This
    auto-enrolls new Sites so a malformed second-site descriptor fails the fast
    unit suite, not only the docs build."""
    site = sd.load(site_path)
    assert site.facility.kind == FacilityKind.SITE.value
    assert site.facility.display_name == site.facility.code


@pytest.mark.parametrize("site_path", _ALL_SITES, ids=lambda p: p.parent.name)
def test_every_site_declares_a_control_plane(site_path: Path) -> None:
    """Every Site declares its control-plane house-style: the software floor
    CORA's edge lands on, a facility-level fact surfaced on the facility page and
    echoed in the landing-page intro's seam beat. Required (not just optional in
    the schema) so a new Site cannot ship without it."""
    control_plane = sd.load(site_path).facility.control_plane
    assert control_plane, f"{site_path.parent.name}: facility.control_plane is missing or empty"


def test_site_loads_and_validates() -> None:
    site = sd.load(_SITE)
    assert site.facility.code == "aps"
    assert site.facility.kind == "Site"
    assert site.facility.control_plane == "EPICS / ophyd"
    # lower bounds, not exact: additive edits should not break this test, except
    # agents which are drift-guarded against the code seeds below. The two
    # non-pending LLM agents are equality-checked in test_agents_match_seed_constants;
    # RunSupervisor + CautionPromoter + ClearanceExpirer + ClearanceWatcher +
    # RunInitiator are authored pending (identity seeded, runtimes not yet operational).
    assert len(site.practices) >= 17
    assert len(site.actors) >= 9
    assert len(site.agents) == 7
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


def _beamline_hosts(facility_code: str) -> list[tuple[str, str]]:
    # The (label, slug) beamlines a facility hosts, for the roster-link guard.
    hosts: list[tuple[str, str]] = []
    for path in sorted((_REPO_ROOT / "deployments").glob("*/beamline.yaml")):
        b = bd.load(path).beamline
        if b.facility == facility_code:
            hosts.append((b.name or path.parent.name, path.parent.name))
    return hosts


def _beamline_refs(facility_code: str) -> list[Any]:
    # Build the roster refs the mkdocs hook would pass for one facility, so the
    # render tests and guards exercise the roster spine, not an empty list.
    # sp.BeamlineRef is dynamically loaded, hence the Any element type.
    refs: list[Any] = []
    for path in sorted((_REPO_ROOT / "deployments").glob("*/beamline.yaml")):
        b = bd.load(path).beamline
        if b.facility == facility_code:
            refs.append(
                sp.BeamlineRef(
                    label=b.name or path.parent.name,
                    slug=path.parent.name,
                    maturity=b.maturity,
                    evidence=b.evidence,
                    coverage=b.coverage,
                    summary=b.summary or "",
                )
            )
    return refs


def _aps_beamline_refs() -> list[Any]:
    return _beamline_refs("aps")


def _render_facility(site_path: Path) -> str:
    site = sd.load(site_path)
    slug = site_path.parent.name
    catalog = cd.load(_CATALOG)
    methods = frozenset(m.name for m in catalog.methods)
    pages = sp.render_all(
        site, slug=slug, catalog_methods=methods, beamlines=_beamline_refs(site.facility.code)
    )
    return pages[f"deployments/{slug}/index.md"]


@pytest.mark.parametrize("site_path", _ALL_SITES, ids=lambda p: p.parent.name)
def test_facility_page_has_no_empty_tables(site_path: Path) -> None:
    """The redesign's core anti-regression: a facility page never renders a table
    header with no body rows. A section with nothing real to show is omitted
    entirely (adaptive rendering), not left as a hollow header + empty table."""
    lines = _render_facility(site_path).splitlines()
    empty: list[str] = []
    for i, line in enumerate(lines):
        # a table is `| ... |` then a `| --- |` separator; the row after the
        # separator must itself be a `| ... |` body row.
        has_sep = i + 2 < len(lines) and lines[i + 1].startswith("| ---")
        is_header = line.startswith("| ") and has_sep
        if is_header and not lines[i + 2].startswith("| "):
            empty.append(line)
    assert not empty, f"{site_path.parent.name}: facility page has empty table(s): {empty}"


@pytest.mark.parametrize("site_path", _ALL_SITES, ids=lambda p: p.parent.name)
def test_facility_page_roster_matches_hosted_beamlines(site_path: Path) -> None:
    """The roster lists exactly the beamlines whose descriptor binds this Site,
    each linked. The facility-page analog of the landing-page badge guard: the
    roster cannot silently drop or invent a beamline."""
    page = _render_facility(site_path)
    hosts = _beamline_hosts(sd.load(site_path).facility.code)
    if not hosts:
        return
    for label, slug in hosts:
        assert f"[{label}](../{slug}/index.md)" in page, (
            f"{site_path.parent.name}: roster missing {label}"
        )


def test_renders_single_site_narrative() -> None:
    site = sd.load(_SITE)
    pages = sp.render_all(
        site,
        catalog_methods=frozenset({"tomography", "dark_field"}),
        beamlines=_aps_beamline_refs(),
    )
    # one reader-first narrative, NOT one page per bounded context
    assert set(pages) == {"deployments/aps/index.md"}
    page = pages["deployments/aps/index.md"]
    assert page.startswith("# APS")
    assert chr(0x2014) not in page
    # the rich pilot Site renders every populated section
    for heading in (
        "## The beamlines",
        "## The techniques adapted here",
        "## What this Site provides",
        "## Safety and governance",
        "## Active cautions",
    ):
        assert heading in page, f"missing section {heading}"
    # roster spine: a beamline row links to the sibling beamline dir with its
    # badges + descriptor summary
    assert "[2-BM](../2-bm/index.md)" in page
    assert "the operational pilot" in page  # 2-BM's descriptor summary, single-sourced
    # both active agents surfaced with their models (the gap-fix)
    assert "CautionDrafter" in page and "claude-sonnet-4-6" in page
    assert "RunDebriefer" in page and "claude-haiku-4-5" in page
    # the deterministic agents are seeded pending; surface them as planned
    for pending_agent in ("RunSupervisor", "ClearanceExpirer", "RunInitiator"):
        assert pending_agent in page, f"pending agent {pending_agent} not surfaced"
    # content woven in from every folded list
    assert "[`tomography`](../../catalog/methods.md)" in page  # practice -> catalog method
    assert "`human`" in page  # principals
    assert "LiquidHelium" in page  # a distinctive supply
    assert "ESAF" in page  # clearances
    assert "beam-flux transients" in page  # cautions
    assert "Institution" in page and "Argonne" in page  # facts header
    assert "Control plane" in page and "EPICS / ophyd" in page  # seam in the facts header
    # the model mapping is one collapsed pointer, no per-page asset table
    assert "## How this maps to CORA's model" in page
    assert "assets.md" not in page


def test_practice_method_links_only_known() -> None:
    site = sd.load(_SITE)
    page = sp.render_all(
        site, catalog_methods=frozenset({"tomography"}), beamlines=_aps_beamline_refs()
    )["deployments/aps/index.md"]
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
    "first_light": "19-BM commissioning method; design phase",
    "ioc_restart": "2-BM maintenance recovery; portable Method not yet authored",
    "mirror_recoat_return": "2-BM mirror recoat-and-return; Method not yet authored",
    "scanning_fluorescence_microscopy": "2-ID + XFM scanning XRF; 2 consumers (METHOD-1)",
    "diffraction": "single-crystal diffraction (4-ID/8-ID/CSX/i19); not yet earned (TECH-1)",
    "magnetic_scattering": "4-ID magnetic scattering; not yet in pilot scope (TECH-1)",
    "resonant_scattering": "4-ID resonant scattering; not yet in pilot scope (TECH-1)",
    "xmcd": "4-ID magnetic circular dichroism; not yet in pilot scope (TECH-1)",
    "xmld": "i06 magnetic linear dichroism on the APPLE-II; not yet in pilot scope (TECH-1)",
    "photoemission_microscopy": "i06 PEEM electron-imaging microscopy; not yet earned (PEEM-1)",
    "reflectivity": "i10 + CMS reflectivity (soft + hard X-ray); rule-of-three watch (TECH-1)",
    "coherent_surface_scattering": "9-ID CSSI surface scattering; not yet in pilot scope (TECH-1)",
    "inelastic_x_ray_scattering": "IXS hard X-ray inelastic scattering; not in scope (TECH-1)",
    "grid_scan": "i03 + FMX + AMX MX fast grid scan; 3 consumers (TECH-1)",
    "mx_data_collection": "i03 + FMX + AMX MX rotation collection; 3 consumers (TECH-1)",
    "sample_exchange": "i03 + FMX + AMX robotic sample exchange; 3 consumers (ROBOT-1)",
    "solution_scattering": "lix bio-SAXS / SEC-SAXS; new Method not yet earned (TECH-1)",
    "x_ray_footprinting": "xfp dose-delivery footprinting; offline MS readout; new Method (TECH-1)",
    "small_angle_scattering": "i22 + 8-ID SAXS; portable Method not yet earned",
    "wide_angle_scattering": "i22 + 9-ID WAXS; portable Method not yet earned",
    "ultra_small_angle_scattering": "12-ID Bonse-Hart USAXS; not yet earned (USAXS-1)",
    "total_scattering": "i15-1 total scattering / PDF; Method not yet earned",
    "energy_dispersive_exafs": "i20-1 EDE; dispersive devices not yet in source (POLY-1 / STRIP-1)",
    "pump_probe": "LCLS-MFX fs optical-laser pump / X-ray probe; XFEL Method not yet earned",
    "xas_spectroscopy": "MFX + ISS emission-spectrometer XAS / XES; 2 consumers (TECH-1)",
    "helical_tomography": "SYRMEP helical large-specimen CT; not yet earned (TECH-1)",
    "white_beam_tomography": "SYRMEP white / pink-beam fast tomography; not yet in scope (TECH-1)",
    "phase_retrieval": "SYRMEP TIE-HOM / Paganin phase retrieval; compute Method (COMPUTE-1)",
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


# ---------------------------------------------------------------------------
# Landing-page facility-card discipline.
#
# docs/deployments/index.md introduces each Site with a short hand-authored card
# that answers three fixed questions: what the facility is, why CORA took it on,
# and its control-plane house-style. The cards grew organically before this
# convention (12 to 205 words, two rival opening formulas, per-beamline detail
# leaking up from the beamline pages). A test cannot judge voice, but it can pin
# the mechanical discipline so a new Site's card cannot balloon or drift back:
#   - bounded length (no card balloons to a mini-essay again),
#   - no "Nth Site" ordinal (the canonical order is the section order, guarded in
#     test_beamline_descriptor; repeating it in prose is the cascade we removed),
#   - no per-beamline slug link (that is beamline-page altitude; the Site's own
#     table already links its beamlines).
# This is the prose analog of the badge-cell / index-drift guards.
# ---------------------------------------------------------------------------

_INDEX = _REPO_ROOT / "docs" / "deployments" / "index.md"
_INTRO_MAX_WORDS = 75
_SITE_ORDINAL_RE = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh|twelfth|thirteenth|fourteenth)\s+Site\b",
    re.IGNORECASE,
)
_BEAMLINE_LINK_RE = re.compile(r"\]\([a-z0-9-]+/index\.md\)")


def _site_intro_cards() -> dict[str, str]:
    # slug -> the intro paragraph under each `## [Site](slug/index.md)` heading,
    # i.e. the text between the heading and the first table / next heading.
    lines = _INDEX.read_text(encoding="utf-8").splitlines()
    cards: dict[str, str] = {}
    heading = re.compile(r"## \[[^\]]+\]\(([^)]+)/index\.md\)")
    i = 0
    while i < len(lines):
        m = heading.match(lines[i])
        if m:
            slug = m.group(1)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            para: list[str] = []
            while (
                j < len(lines)
                and lines[j].strip()
                and not lines[j].startswith("|")
                and not lines[j].startswith("##")
            ):
                para.append(lines[j])
                j += 1
            cards[slug] = " ".join(para)
        i += 1
    return cards


def test_site_intro_cards_exist_for_every_site() -> None:
    cards = _site_intro_cards()
    site_slugs = {p.parent.name for p in _ALL_SITES}
    missing = sorted(site_slugs - set(cards))
    assert not missing, f"Sites with no intro card on docs/deployments/index.md: {missing}"
    # anchor so the discipline checks below cannot pass vacuously on an empty parse
    assert len(cards) >= len(site_slugs)


def test_site_intro_cards_are_disciplined() -> None:
    problems: list[str] = []
    for slug, text in _site_intro_cards().items():
        words = len(text.split())
        if words > _INTRO_MAX_WORDS:
            problems.append(f"{slug}: intro is {words} words (max {_INTRO_MAX_WORDS})")
        if _SITE_ORDINAL_RE.search(text):
            problems.append(
                f"{slug}: intro states an 'Nth Site' ordinal (drop it; order is canonical)"
            )
        if _BEAMLINE_LINK_RE.search(text):
            problems.append(
                f"{slug}: intro links a beamline page (that is beamline-altitude detail)"
            )
    assert not problems, "facility-card discipline violations:\n" + "\n".join(problems)


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
