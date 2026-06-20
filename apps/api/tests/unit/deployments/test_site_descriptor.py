"""Guards for the site descriptor (deployments/aps/site.yaml).

Four kinds of guard, matching the no-drift boundary:
  - round-trip: the descriptor loads and validates against its schema.
  - enum-equality: the closed-vocabulary frozensets mirrored in
    scripts/site_descriptor.py equal their cora enums (FacilityKind, ActorKind).
  - agent drift-guard: the agents authored in site.yaml equal the code seeds
    (RunDebriefer + CautionDrafter), so a seeded agent missing from the docs (or
    a model / version / kind drift between code and docs) fails the build.
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


def test_site_loads_and_validates() -> None:
    site = sd.load(_SITE)
    assert site.facility.code == "aps"
    assert site.facility.kind == "Site"
    # lower bounds, not exact: additive edits should not break this test, except
    # agents which are drift-guarded against the code seeds below. The two
    # non-pending LLM agents are equality-checked in test_agents_match_seed_constants;
    # RunSupervisor + CautionPromoter are authored pending (identity seeded,
    # runtimes not yet operational).
    assert len(site.practices) >= 17
    assert len(site.actors) >= 9
    assert len(site.agents) == 4
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
    pages = sp.render_all(site, catalog_methods=frozenset({"tomography", "dark_baseline"}))
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
    # both agents surfaced with their models (the gap-fix)
    assert "CautionDrafter" in page and "claude-sonnet-4-6" in page
    assert "RunDebriefer" in page and "claude-haiku-4-5" in page
    # content woven in from every folded list
    assert "[`tomography`](../../catalog/methods.md)" in page  # practice -> catalog method
    assert "`human`" in page  # principals
    assert "LiquidHelium" in page  # supplies
    assert "ESAF" in page  # clearances
    assert "beam-flux transients" in page  # cautions
    assert "Institution" in page and "Argonne" in page  # facility -> institution (context)
    assert "../argonne/index.md" not in page  # institution is context, not a navigable deployment


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
