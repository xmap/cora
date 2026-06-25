"""Round-trip test for the beamline descriptor schema and renderer.

The descriptor at deployments/2-bm/beamline.yaml is the single source the docs
build renders from. This test loads it through the same scripts/ modules the
mkdocs on_files hook uses, asserting it validates and renders, that the
new/confirm markers survived as real fields, and that a malformed descriptor
fails loudly. It is a pure parser test (no I/O beyond reading the file), hence
the unit tier.

The scripts/ modules are loaded via importlib (the dynamic-import bridge used by
tests/integration/scenarios/conftest.py), since scripts/ is not on the
type-checker's path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
import yaml

from cora.equipment.aggregates._drawing import DrawingSystem

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_DEPLOYMENTS = _REPO_ROOT / "deployments"
_DESCRIPTOR = _DEPLOYMENTS / "2-bm" / "beamline.yaml"
_CATALOG = _REPO_ROOT / "catalog" / "catalog.yaml"


def _beamline_descriptors() -> list[Path]:
    # Every deployment's beamline descriptor. The catalog cross-checks run per
    # descriptor so a second beamline cannot drift its model/family bindings
    # unguarded; the 2-BM-only _DESCRIPTOR is kept for 2-BM-specific content.
    return sorted(_DEPLOYMENTS.glob("*/beamline.yaml"))


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bd = _load("beamline_descriptor")
bp = _load("beamline_pages")
cd = _load("catalog_descriptor")
sd = _load("site_descriptor")


def _render_with_catalog() -> str:
    descriptor = bd.load(_DESCRIPTOR)
    catalog = cd.load(_CATALOG)
    pages = bp.render_all(
        descriptor,
        catalog_families=frozenset(f.name for f in catalog.families),
        catalog_models=frozenset(m.name for m in catalog.models),
    )
    return pages["deployments/2-bm/beamline.md"]


def _humanize(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").strip().capitalize()


def _walk_devices(descriptor: Any) -> list[Any]:
    # Every modelled device in the descriptor: the beam-walk groups plus the
    # cross-cutting controls section (motion controllers, triggering), recursing
    # into nested constituents (the P6-50 SafetyStack, the Microscope chain) so a
    # drift on a controls device or a nested constituent cannot hide from the
    # catalog cross-checks below.
    found: list[Any] = []

    def visit(device: Any) -> None:
        found.append(device)
        constituents: list[Any] = device.constituents or []
        for constituent in constituents:
            visit(constituent)

    for _name, group in descriptor.groups:
        for device in group.devices:
            visit(device)
    controls = descriptor.controls
    if controls is not None:
        for device in (*controls.motion_controllers, *controls.triggering):
            visit(device)
    return found


def test_descriptor_loads_and_validates() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    assert descriptor.beamline.name == "2-BM"
    assert descriptor.beamline.facility == "aps"
    assert descriptor.groups, "expected at least one beam-path group"
    group_names = [name for name, _ in descriptor.groups]
    for expected in (
        "front-end",
        "conditioning-optics",
        "beam-defining-and-safety",
        "sample-environment",
        "detector",
    ):
        assert expected in group_names
    assert descriptor.controls is not None
    assert descriptor.resources is not None


def test_enclosures_carry_facility_code_and_permit_pv() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    enclosures = {e.name: e for e in descriptor.enclosures}
    assert {"2-BM-A", "2-BM-B"} <= set(enclosures)
    for name in ("2-BM-A", "2-BM-B"):
        assert enclosures[name].facility_code == "aps"
    # the per-hutch search-and-secure permit PVs are confirmed post-migration (PSS-1)
    assert enclosures["2-BM-A"].permit_signal == "S02BM-PSS:StaA:SecureM"
    assert enclosures["2-BM-B"].permit_signal == "S02BM-PSS:StaB:SecureM"


def test_unknown_enclosure_ref_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad_enclosure_ref.yaml"
    bad.write_text(
        "beamline:\n  name: T\n"
        "enclosures:\n  - name: hutch-a\n    facility_code: aps\n"
        "front-end:\n  enclosure: not-declared\n  devices: []\n",
        encoding="utf-8",
    )
    with pytest.raises(bd.DescriptorError):
        bd.load(bad)


def test_renders_enclosures_table_facility_and_permit_columns() -> None:
    markdown = _render_with_catalog()
    assert "## Enclosures" in markdown
    assert "| Enclosure | Role | Facility | Permit signal |" in markdown
    # each hutch row carries its containing-Facility slug and its permit PV
    assert "`2-BM-A`" in markdown
    assert "`2-BM-B`" in markdown
    assert "`aps`" in markdown
    assert "`S02BM-PSS:StaA:SecureM`" in markdown
    assert "`S02BM-PSS:StaB:SecureM`" in markdown


def test_renders_source_stage_walk_and_no_em_dash() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    markdown = _render_with_catalog()

    # The generated page is the Source stage; the sample and detection stages are
    # the composed-fixture pages (equipment/sample_tower.md, equipment/microscope.md).
    assert markdown.startswith("# Source")
    source_groups = [name for name, group in descriptor.groups if group.stage == "source"]
    downstream_groups = [name for name, group in descriptor.groups if group.stage != "source"]
    assert len(source_groups) >= 2
    for name in source_groups:
        assert f"## {_humanize(name)}" in markdown
    for name in downstream_groups:
        assert f"## {_humanize(name)}" not in markdown
    # the generated Source page is beam-devices-only: controllers live on the
    # Controls page and supplies in Operations, so neither section renders here
    assert "## Controls" not in markdown
    assert "## Resources" not in markdown
    # a source device and a promoted marker tag render; downstream-stage devices do
    # not (they live on the fixture pages)
    assert "`FrontEndShutter`" in markdown
    assert "`SampleTop_X`" not in markdown
    assert "`Objective_Selector`" not in markdown
    assert "`new`" in markdown
    # the P6-50 nested constituents (a source-stage device) render as their own sub-table
    assert "**SafetyStack constituents**" in markdown
    # a source family present in the Catalog links up; a pending one renders plain (no fake link).
    # Beam is the loose bending-magnet source representation, intentionally never a catalog Family
    # (see the InsertionDevice family note), so it is a stable "renders plain" example.
    assert "](../../catalog/families.md)" in markdown
    assert "`Beam`" in markdown
    assert "[`Beam`](../../catalog/families.md)" not in markdown
    # the folded source-area modelling note and the confirm marker render
    assert "no Conditioner Role" in markdown
    assert "`confirm`" in markdown
    # repo style: no em dashes in generated prose (chr() keeps the literal out of source)
    assert chr(0x2014) not in markdown


def test_markers_promoted_from_comments_to_fields() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    devices = {d.name: d for _name, group in descriptor.groups for d in group.devices}
    assert devices["source"].new is True
    assert bool(devices["BeamPositionMonitor"].confirm) is True
    # Mask carries new (not yet a registered Asset) but no confirm marker: its
    # values are staff-verified (ALIGN-2).
    assert devices["Mask"].new is True
    assert devices["Mask"].confirm is False
    # a solid CORA-modeled device carries neither marker
    assert devices["SampleTop_X"].new is False
    assert devices["SampleTop_X"].confirm is False


def test_drawing_system_mirror_matches_code() -> None:
    assert {d.value for d in DrawingSystem} == bd.DRAWING_SYSTEMS


def test_drawings_and_calibrations_loaded() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    devices = {d.name: d for _name, group in descriptor.groups for d in group.devices}
    obj0 = devices["Objective_10x"]
    assert obj0.drawing is not None
    assert obj0.drawing.system == "EDMS"
    assert obj0.calibrations
    assert obj0.calibrations[0].quantity == "magnification"
    assert devices["Hexapod"].drawing is not None


def test_at_least_one_beamline_descriptor_found() -> None:
    # The catalog cross-checks below are parametrized over discovered
    # descriptors; an empty glob would make them all vanish and pass vacuously.
    assert _beamline_descriptors(), "no deployments/*/beamline.yaml found"


def test_walk_reaches_2bm_devices_across_sections() -> None:
    # Anchor the device walk to known 2-BM content so it cannot silently
    # regress to empty (which would make the resolution checks vacuous): the
    # walk must reach a beam-path device, a nested constituent, and a controls
    # device.
    devices = _walk_devices(bd.load(_DESCRIPTOR))
    names = {d.name for d in devices}
    assert {"Turret", "StationShutter", "RotaryDrive"} <= names
    assert sum(1 for d in devices if d.model) >= 5


@pytest.mark.parametrize("descriptor_path", _beamline_descriptors(), ids=lambda p: p.parent.name)
def test_device_model_references_resolve_in_catalog(descriptor_path: Path) -> None:
    descriptor = bd.load(descriptor_path)
    catalog = cd.load(_CATALOG)
    model_names = {m.name for m in catalog.models}
    dangling = sorted(
        f"{d.name} -> {d.model}"
        for d in _walk_devices(descriptor)
        if d.model and d.model not in model_names
    )
    assert not dangling, (
        f"{descriptor_path.parent.name}: devices bind catalog models that do not exist: {dangling}"
    )


@pytest.mark.parametrize("descriptor_path", _beamline_descriptors(), ids=lambda p: p.parent.name)
def test_device_family_is_declared_by_its_bound_model(descriptor_path: Path) -> None:
    descriptor = bd.load(descriptor_path)
    catalog = cd.load(_CATALOG)
    declared = {m.name: set(m.declared_families) for m in catalog.models}
    mismatched = sorted(
        f"{d.name}: family {d.family} not in {sorted(declared[d.model])} (model {d.model})"
        for d in _walk_devices(descriptor)
        if d.model and d.family and d.model in declared and d.family not in declared[d.model]
    )
    assert not mismatched, (
        f"{descriptor_path.parent.name}: device family disagrees with bound model's "
        f"declared_families: {mismatched}"
    )


# Catalog models bound by no deployment device today. Each is a rename-trap
# landing pad, so a NEW orphan must be bound, removed, or added here with a
# reason. The two non-kit entries are catalog models whose 2-BM devices are not
# yet model-bound (a descriptor follow-up, distinct from the kit alternatives).
_ALLOWED_ORPHAN_MODELS = {
    "aerotech_abrs150mp": "rotary swap-kit alternative; installed rotary is ABRS-250MP",
    "aerotech_abs2000": "rotary swap-kit alternative; installed rotary is ABRS-250MP",
    "mitutoyo_plan_apo": "objective product-line model; Objective_* devices not yet model-bound",
    "crytur_luag": "scintillator model; Scintillator device not yet model-bound",
}


def _count_binding_keys(node: Any) -> dict[str, int]:
    # Count mappings carrying a non-null model:/family: anywhere in the raw YAML.
    # Compared against the typed walk to catch a binding hidden under an untyped
    # extra= key (e.g. a device-dict in a stray group key) that the walk misses.
    counts = {"model": 0, "family": 0}

    def visit(n: Any) -> None:
        if isinstance(n, dict):
            mapping = cast("dict[str, Any]", n)
            for key in counts:
                if mapping.get(key) is not None:
                    counts[key] += 1
            for value in mapping.values():
                visit(value)
        elif isinstance(n, list):
            for value in cast("list[Any]", n):
                visit(value)

    visit(node)
    return counts


def _catalog_marker_models(md_path: Path) -> list[str]:
    # Model names listed in every `catalog:models models=...` marker on the page.
    # The vendor tables are build-generated from these lists, so the marker is the
    # hand-authored surface a stale Model id would land on.
    names: list[str] = []
    for line in md_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("<!-- catalog:models"):
            continue
        for token in stripped.split():
            key, _, value = token.partition("=")
            if key == "models" and value:
                names.extend(name for name in value.split(",") if name)
    return names


def test_no_unexpected_orphan_catalog_models() -> None:
    catalog = cd.load(_CATALOG)
    bound = {
        device.model
        for path in _beamline_descriptors()
        for device in _walk_devices(bd.load(path))
        if device.model
    }
    orphans = {m.name for m in catalog.models} - bound
    unexpected = orphans - set(_ALLOWED_ORPHAN_MODELS)
    assert not unexpected, (
        "catalog models bound by no deployment device (rename-trap landing pads); "
        f"bind, remove, or allowlist with a reason: {sorted(unexpected)}"
    )
    stale_allowlist = set(_ALLOWED_ORPHAN_MODELS) - orphans
    assert not stale_allowlist, (
        f"bound or removed; drop from _ALLOWED_ORPHAN_MODELS: {sorted(stale_allowlist)}"
    )


# ---------------------------------------------------------------------------
# Family integrity and federation-alignment guards.
#
# A device family with NO bound model is otherwise checked against nothing
# (test_device_family_is_declared_by_its_bound_model fires only when a model is
# bound), so a typo'd or synonym family would pass silently. These guards make
# every loose family (a family string not in the catalog) a deliberate, reasoned
# registry entry, surface promotion candidates as the fleet grows, and keep the
# beamline -> site facility pointer resolvable. They mirror the two-sided
# orphan-model guard above (assert no unexpected AND no stale allowlist entry).
# ---------------------------------------------------------------------------

PROMOTION_THRESHOLD = 2

# Loose families: a device family string that is not (yet) a catalog Family.
# Each is either a Supply observation that never becomes an Asset Family, a
# passive beam-path element deferred under that tier, or a real candidate staged
# behind an open question (the bucket leads each reason). A NEW loose family must
# land here with a reason: that forces a synonym or typo to surface in review
# without forcing premature promotion into the catalog.
_ALLOWED_LOOSE_FAMILIES = {
    "Beam": "supply: Supply(PhotonBeam) source observation; never an Asset Family",
    "Vacuum": "supply: Supply(Vacuum) observation; never an Asset Family",
    "StorageRing": "supply: machine-level observe-only ring state (MACHINE-1); not an Asset Family",
    "HeatAbsorber": "passive-deferred: passive beam-path tier (TomoWISE front-end absorber)",
    "SafetyStack": "passive-deferred: passive safety composite (2-BM P6-50)",
    "Shielding": "passive-deferred: passive PSS-grade shielding (19-BM guillotines, ENC-1)",
    "SlipRing": "passive-deferred: passive rotation feedthrough (TomoWISE)",
    "Wedge": "passive-deferred: passive fixed wedge (2-BM)",
    "Diagnostic": "staged: beam-position monitor, Sensor Role; fold-vs-promote open (DIAG-1)",
    "FlowController": "staged: settable flow/pump actuator; earn-vs-defer open (FLOW-1/ENV-1)",
    "Backlight": "staged: new illumination affordance; rule-of-three open (ROBOT-1/DET-1)",
    "BetrandLens": "staged: novel TXM optic, FXI-only; rule-of-three open (OPTIC-3)",
    "MultilayerLaueLens": "staged: novel 1D crossed-pair nano-focus optic, HXN-only (OPTIC-3)",
    "Chopper": "staged: rotary duty-cycle device; fold-vs-Family open (CHOP-1)",
    "Photodiode": "staged: PIN photodiode, Sensor Role; Family-vs-Sensor open (RAD-1)",
    "Transfocator": "staged: compound-refractive-lens optic; no catalog home yet (CRL-1)",
    "EmissionSpectrometer": "staged: crystal-analyzer emission spectrometer; new (SPEC-1)",
    "Baffle": "staged: passive baffle inside the 2-BM SafetyStack; review name/role",
    "Screen": "staged: motorized phosphor diagnostic flag (2-BM, FLAG-1); review name-vs-behavior",
    "BeamPositionMonitor": "staged: position/intensity Sensor; fold-vs-promote open (DIAG-1)",
    "PhaseRetarder": "staged: polarization phase-retarder (4-ID); rule-of-three open (POL-1)",
    "PolarizationAnalyzer": "staged: polarization analyzer (4-ID); rule-of-three open (POL-2)",
    "Magnet": "staged: sample-environment magnet (4-ID POLAR); rule-of-three open (MAG-1)",
    "Laser": "staged: pump-probe laser (4-ID POLAR); model-vs-hazard open (SAMPLE-1)",
    "Rheometer": "staged: rheometer shear-cell (8-ID); rule-of-three open (SAMPLE-1)",
    "FlightPath": "staged: evacuated XPCS flight path (8-ID); rule-of-three open (XPCS-2)",
    "SpectrometerArm": "staged: energy-dispersive RIXS arm (SIX); no point-Sensor fit (RIXS-1)",
    "ElectronAnalyzer": "staged: electron energy analyzer (ESM); not a photon detector (ARPES-1)",
    "EnergyAnalyzer": "staged: IXS diced crystal energy analyzer; n=1 (ANALYZER-1)",
}

# The subset of loose families that is conceptually a Supply observation (a
# facility resource or machine state), not an Asset, so it never counts toward
# catalog promotion.
_SUPPLY_LOOSE_FAMILIES = {"Beam", "Vacuum", "StorageRing"}

# Loose families that have reached the promotion threshold and whose
# promote-or-hold decision has been recorded. A non-supply loose family that
# crosses PROMOTION_THRESHOLD deployments fails the build until it is either
# graduated into the catalog or recorded here with a one-line decision: the
# signal is mechanical, the decision stays human.
_PROMOTION_REVIEWED = {
    "Diagnostic": "hold: Sensor fold-vs-promote still open (DIAG-1)",
    "Screen": "hold: phosphor beam-viewing screen (2-BM, BMM); fold-vs-promote open (FLAG-1)",
    "FlowController": "hold: earn-vs-defer still open (FLOW-1)",
    "Transfocator": "hold: CRL optic abstraction still open across i22/4-id/8-id/9-id (CRL-1)",
    "BeamPositionMonitor": "hold: Sensor fold-vs-promote across 4-id/8-id/9-id (DIAG-1/FLUX-1)",
    "Laser": "hold: pump-probe laser model-vs-hazard open (4-id + lcls-mfx; SAMPLE-1)",
    "Backlight": "hold: sample-illumination affordance fold-vs-promote open (i03 + i24; DET-1)",
    "ElectronAnalyzer": "hold: e- analyzer at n=2 (esm + sst); graduation candidate (ARPES-1)",
}

# Catalog families bound by no deployment device. Symmetric to the orphan-model
# guard: an un-earned family contradicts "the model only contains what a real
# deployment forced." Empty today (GenericProbe is bound by FXI flux monitors).
_ALLOWED_ORPHAN_FAMILIES: dict[str, str] = {}


def _classify(observed: set[str], allowed: set[str]) -> tuple[list[str], list[str]]:
    # (unexpected, stale): observed-not-allowed, allowed-not-observed. The shared
    # core of the two-sided allowlist guards, unit-tested on synthetic input below
    # so a future refactor cannot quietly weaken them.
    return sorted(observed - allowed), sorted(allowed - observed)


def _catalog_family_names() -> set[str]:
    return {f.name for f in cd.load(_CATALOG).families}


def _used_families() -> set[str]:
    return {
        device.family
        for path in _beamline_descriptors()
        for device in _walk_devices(bd.load(path))
        if device.family
    }


def _loose_family_deployments() -> dict[str, set[str]]:
    # family (not in the catalog) -> the deployments that bind it.
    catalog_families = _catalog_family_names()
    spread: dict[str, set[str]] = {}
    for path in _beamline_descriptors():
        deployment = path.parent.name
        for device in _walk_devices(bd.load(path)):
            family = device.family
            if family and family not in catalog_families:
                spread.setdefault(family, set()).add(deployment)
    return spread


def _site_descriptors() -> list[Path]:
    return sorted(_DEPLOYMENTS.glob("*/site.yaml"))


def _site_facility_codes() -> set[str]:
    return {sd.load(path).facility.code for path in _site_descriptors()}


def test_no_unexpected_loose_families() -> None:
    loose = _used_families() - _catalog_family_names()
    unexpected, stale = _classify(loose, set(_ALLOWED_LOOSE_FAMILIES))
    assert not unexpected, (
        "device families not in the catalog and not allowlisted (a typo, a synonym, or a "
        "genuinely new device class); add to catalog.families or to _ALLOWED_LOOSE_FAMILIES "
        f"with a reason: {unexpected}"
    )
    assert not stale, (
        f"promoted into the catalog or no longer used; drop from _ALLOWED_LOOSE_FAMILIES: {stale}"
    )


def test_loose_families_past_promotion_threshold_are_reviewed() -> None:
    spread = _loose_family_deployments()
    candidates = {
        family
        for family, deployments in spread.items()
        if len(deployments) >= PROMOTION_THRESHOLD and family not in _SUPPLY_LOOSE_FAMILIES
    }
    unreviewed = sorted(
        f"{family} {sorted(spread[family])}"
        for family in candidates
        if family not in _PROMOTION_REVIEWED
    )
    assert not unreviewed, (
        f"loose families at >= {PROMOTION_THRESHOLD} deployments with no recorded decision; "
        "graduate them into catalog.families or record a promote-or-hold note in "
        f"_PROMOTION_REVIEWED: {unreviewed}"
    )
    stale = sorted(set(_PROMOTION_REVIEWED) - candidates)
    assert not stale, (
        "no longer a sub-threshold candidate (promoted, removed, or now a Supply family); "
        f"drop from _PROMOTION_REVIEWED: {stale}"
    )


def test_no_unexpected_orphan_catalog_families() -> None:
    orphans = _catalog_family_names() - _used_families()
    unexpected, stale = _classify(orphans, set(_ALLOWED_ORPHAN_FAMILIES))
    assert not unexpected, (
        "catalog families bound by no deployment device (un-earned abstractions); "
        f"bind, remove, or allowlist with a reason: {unexpected}"
    )
    assert not stale, f"now bound or removed; drop from _ALLOWED_ORPHAN_FAMILIES: {stale}"


def test_site_facility_codes_cover_known_sites() -> None:
    # Anchor so the resolution check below cannot pass vacuously on an empty set.
    assert {"aps", "diamond", "maxiv", "nsls2", "slac"} <= _site_facility_codes()


@pytest.mark.parametrize("descriptor_path", _beamline_descriptors(), ids=lambda p: p.parent.name)
def test_beamline_and_enclosure_facility_codes_resolve(descriptor_path: Path) -> None:
    descriptor = bd.load(descriptor_path)
    codes = _site_facility_codes()
    deployment = descriptor_path.parent.name
    unresolved: list[str] = []
    facility = descriptor.beamline.facility
    if facility is not None and facility not in codes:
        unresolved.append(f"beamline.facility={facility!r}")
    for enclosure in descriptor.enclosures:
        code = enclosure.facility_code
        if code is not None and code not in codes:
            unresolved.append(f"enclosure {enclosure.name}.facility_code={code!r}")
    assert not unresolved, (
        f"{deployment}: facility pointer(s) do not resolve to a site.yaml facility.code "
        f"{sorted(codes)}: {unresolved}"
    )


def test_allowlist_guard_logic_detects_unexpected_and_stale() -> None:
    # The two-sided guards reduce to _classify; prove it on synthetic input.
    # "Scintilator" is the canonical typo of the catalog family Scintillator.
    unexpected, stale = _classify({"Scintilator", "Beam"}, {"Beam"})
    assert unexpected == ["Scintilator"]
    assert stale == []
    unexpected, stale = _classify(set(), {"GoneFamily"})
    assert unexpected == []
    assert stale == ["GoneFamily"]


# ---------------------------------------------------------------------------
# Descriptor <-> deployment-docs drift guard.
#
# Each deployment's docs/deployments/<id>/ pages carry a hand-authored, curated
# inventory (editorial columns, live condition, and, for the operational pilot,
# derived PseudoAxis Assets that exist only in scenario setup), so they are NOT
# generated from the descriptor. This guard keeps only the factual subset honest:
# every device the descriptor MODELS (not marked new:, i.e. a real CORA Asset or
# a live verified device) must be mentioned by name somewhere in its deployment
# docs, so renaming or removing a device in the descriptor cannot leave a stale
# doc, and a documented Asset cannot quietly lose its descriptor source. Devices
# marked new: are not yet modelled and are legitimately absent, so a pure
# design-phase scaffold (all-new) is not pinned until its devices materialize.
# ---------------------------------------------------------------------------

_DOCS_DEPLOYMENTS = _REPO_ROOT / "docs" / "deployments"


def _deployment_doc_text(deployment: str) -> str:
    base = _DOCS_DEPLOYMENTS / deployment
    if not base.is_dir():
        return ""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(base.rglob("*.md")))


@pytest.mark.parametrize("descriptor_path", _beamline_descriptors(), ids=lambda p: p.parent.name)
def test_modeled_devices_are_documented(descriptor_path: Path) -> None:
    deployment = descriptor_path.parent.name
    doc_text = _deployment_doc_text(deployment)
    assert doc_text, f"{deployment}: no docs/deployments/{deployment}/*.md found"
    descriptor = bd.load(descriptor_path)
    missing = sorted(
        device.name
        for device in _walk_devices(descriptor)
        if device.name and not device.new and f"`{device.name}`" not in doc_text
    )
    assert not missing, (
        f"{deployment}: modelled devices (no new: marker) absent from "
        f"docs/deployments/{deployment}/ as a `name` mention; document them or mark new: in "
        f"the descriptor: {missing}"
    )


def test_modeled_device_documentation_is_not_vacuous() -> None:
    # The operational pilot models many devices; pin a floor so the per-deployment
    # check above cannot quietly go vacuous (every device flipped to new:, or the
    # doc glob breaking) and pass without checking anything.
    modeled = [d for d in _walk_devices(bd.load(_DESCRIPTOR)) if d.name and not d.new]
    assert len(modeled) >= 30, f"expected the 2-BM pilot to model many devices, got {len(modeled)}"


@pytest.mark.parametrize("descriptor_path", _beamline_descriptors(), ids=lambda p: p.parent.name)
def test_no_model_or_family_binding_escapes_the_walk(descriptor_path: Path) -> None:
    raw = yaml.safe_load(descriptor_path.read_text(encoding="utf-8"))
    raw_counts = _count_binding_keys(raw)
    walked = _walk_devices(bd.load(descriptor_path))
    walked_counts = {
        "model": sum(1 for d in walked if d.model),
        "family": sum(1 for d in walked if d.family),
    }
    assert raw_counts == walked_counts, (
        f"{descriptor_path.parent.name}: a model/family binding sits off the device walk "
        f"(raw {raw_counts} vs walked {walked_counts}); it would escape the catalog checks"
    )


def test_doc_catalog_markers_reference_real_catalog_models() -> None:
    catalog = cd.load(_CATALOG)
    model_names = {m.name for m in catalog.models}
    docs_deployments = _REPO_ROOT / "docs" / "deployments"
    stale: list[str] = []
    markers_seen = 0
    for md_path in sorted(docs_deployments.rglob("*.md")):
        listed = _catalog_marker_models(md_path)
        if listed:
            markers_seen += 1
        stale.extend(
            f"{md_path.relative_to(_REPO_ROOT)}: {name}"
            for name in listed
            if name not in model_names
        )
    assert markers_seen >= 1, "no catalog:models markers found to check"
    assert not stale, f"catalog:models markers reference models that do not exist: {stale}"


def test_malformed_descriptor_raises(tmp_path: Path) -> None:
    missing_beamline = tmp_path / "no_beamline.yaml"
    missing_beamline.write_text("enclosures: []\n", encoding="utf-8")
    with pytest.raises(bd.DescriptorError):
        bd.load(missing_beamline)

    missing_name = tmp_path / "no_name.yaml"
    missing_name.write_text("beamline:\n  facility: aps\n", encoding="utf-8")
    with pytest.raises(bd.DescriptorError):
        bd.load(missing_name)
