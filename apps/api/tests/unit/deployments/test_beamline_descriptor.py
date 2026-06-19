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
    # a source family present in the Catalog links up; a pending one renders plain (no fake link)
    assert "](../../catalog/families.md)" in markdown
    assert "`Mask`" in markdown
    assert "[`Mask`](../../catalog/families.md)" not in markdown
    # the folded source-area modelling note and a confirm note render
    assert "no Conditioner Role" in markdown
    assert "confirm: count and thickness" in markdown
    # repo style: no em dashes in generated prose (chr() keeps the literal out of source)
    assert chr(0x2014) not in markdown


def test_markers_promoted_from_comments_to_fields() -> None:
    descriptor = bd.load(_DESCRIPTOR)
    devices = {d.name: d for _name, group in descriptor.groups for d in group.devices}
    assert devices["source"].new is True
    assert bool(devices["Mask"].confirm) is True
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


def _model_column_cells(md_path: Path) -> list[str]:
    # First-column ids of every hand-authored "| Model | ... |" vendor table.
    cells: list[str] = []
    in_table = False
    for line in md_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("| Model |"):
            in_table = True
            continue
        if not in_table:
            continue
        if not stripped.startswith("|"):
            in_table = False
            continue
        if not stripped.replace("|", "").replace("-", "").strip():
            continue  # the header separator row
        cell = stripped.split("|")[1].strip().strip("`")
        if cell:
            cells.append(cell)
    return cells


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


def test_doc_vendor_tables_reference_real_catalog_models() -> None:
    catalog = cd.load(_CATALOG)
    model_names = {m.name for m in catalog.models}
    docs_deployments = _REPO_ROOT / "docs" / "deployments"
    stale: list[str] = []
    tables_seen = 0
    for md_path in sorted(docs_deployments.rglob("*.md")):
        cells = _model_column_cells(md_path)
        if cells:
            tables_seen += 1
        stale.extend(
            f"{md_path.relative_to(_REPO_ROOT)}: {cell}"
            for cell in cells
            if cell not in model_names
        )
    assert tables_seen >= 1, "no hand-authored Model-column vendor tables found to check"
    assert not stale, f"doc vendor tables reference catalog models that do not exist: {stale}"


def test_malformed_descriptor_raises(tmp_path: Path) -> None:
    missing_beamline = tmp_path / "no_beamline.yaml"
    missing_beamline.write_text("enclosures: []\n", encoding="utf-8")
    with pytest.raises(bd.DescriptorError):
        bd.load(missing_beamline)

    missing_name = tmp_path / "no_name.yaml"
    missing_name.write_text("beamline:\n  facility: aps\n", encoding="utf-8")
    with pytest.raises(bd.DescriptorError):
        bd.load(missing_name)
