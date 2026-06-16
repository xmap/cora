"""Guards for the catalog descriptor (catalog/catalog.yaml).

Three kinds of guard, matching the no-drift boundary:
  - round-trip: the descriptor loads and validates against its schema.
  - enum-equality: the closed-vocabulary frozensets mirrored in
    scripts/catalog_descriptor.py equal their cora enums (so a hand-edited
    mirror cannot silently rot, e.g. when a 30th Affordance lands).
  - roles drift-guard: the roles authored in catalog.yaml equal the code's
    SEED_ROLES (the one catalog kind with a global code seed).

The scripts/ module is loaded via importlib (scripts/ is not on the
type-checker's path); the cora enums + SEED_ROLES are imported normally.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from cora.equipment.aggregates.assembly.state import SlotCardinality
from cora.equipment.aggregates.family.affordance import Affordance
from cora.equipment.aggregates.model.state import ManufacturerIdentifierType
from cora.equipment.aggregates.role import SEED_ROLES
from cora.recipe.aggregates.capability.executor_shape import ExecutorShape

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_CATALOG = _REPO_ROOT / "catalog" / "catalog.yaml"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cd = _load("catalog_descriptor")
cp = _load("catalog_pages")


def _vals(items: Any) -> set[str]:
    """Stringify a collection of enums / VOs / strings to a comparable set."""
    return {str(getattr(x, "value", x)) for x in items}


def test_catalog_loads_and_validates() -> None:
    cat = cd.load(_CATALOG)
    assert len(cat.roles) == 4
    assert {r.name for r in cat.roles} == {"Detector", "Positioner", "Controller", "Sensor"}
    # lower bounds, not exact: additive catalog edits should not break this test
    # (only roles == 4 is exact, because it is drift-guarded against SEED_ROLES).
    assert len(cat.families) >= 10
    assert len(cat.capabilities) >= 5
    assert len(cat.methods) >= 15
    assert len(cat.models) >= 12
    assert len(cat.assemblies) >= 2
    assert {a.name for a in cat.assemblies} >= {"Microscope", "Optics"}
    # every method references a capability that exists in the catalog
    codes = {c.code for c in cat.capabilities}
    for m in cat.methods:
        assert m.capability in codes, f"{m.name} -> unknown capability {m.capability}"


def test_affordance_mirror_matches_code() -> None:
    assert {a.value for a in Affordance} == cd.AFFORDANCES


def test_executor_shape_mirror_matches_code() -> None:
    assert {e.value for e in ExecutorShape} == cd.EXECUTOR_SHAPES


def test_manufacturer_id_type_mirror_matches_code() -> None:
    assert {t.value for t in ManufacturerIdentifierType} == cd.MANUFACTURER_ID_TYPES


def test_slot_cardinality_mirror_matches_code() -> None:
    assert {c.value for c in SlotCardinality} == cd.SLOT_CARDINALITIES


def test_roles_match_seed_roles() -> None:
    cat = cd.load(_CATALOG)
    authored = {r.name: r for r in cat.roles}
    seeded = {str(getattr(r.name, "value", r.name)): r for r in SEED_ROLES}
    assert set(authored) == set(seeded)
    for name, seed in seeded.items():
        role = authored[name]
        assert role.docstring == seed.docstring, f"{name} docstring drift"
        assert set(role.required_affordances) == _vals(seed.required_affordances)
        assert set(role.optional_affordances) == _vals(seed.optional_affordances)
        assert set(role.produces) == _vals(seed.produces)
        assert set(role.consumes) == _vals(seed.consumes)


def test_renders_all_catalog_pages() -> None:
    cat = cd.load(_CATALOG)
    pages = cp.render_all(cat)
    assert set(pages) == {
        "catalog/capabilities.md",
        "catalog/methods.md",
        "catalog/families.md",
        "catalog/assemblies.md",
        "catalog/roles.md",
        "catalog/models.md",
    }
    for src_uri, markdown in pages.items():
        assert markdown.startswith("# "), f"{src_uri} missing H1"
        assert chr(0x2014) not in markdown, f"{src_uri} has an em dash"
    # spot-check derived + per-item content actually rendered
    assert "`tomography`" in pages["catalog/capabilities.md"]
    assert "depth-of-focus" in pages["catalog/methods.md"]
    assert "`Imageable`" in pages["catalog/roles.md"]
    assert "Aerotech" in pages["catalog/models.md"]
    assemblies_md = pages["catalog/assemblies.md"]
    assert "`Microscope`" in assemblies_md
    assert "`Optics`" in assemblies_md
    assert "`Detector`" in assemblies_md  # Microscope presents_as
    assert "`optics` -> `Optics`" in assemblies_md  # sub-assembly link rendered


def test_catalog_guards_reject_bad_data(tmp_path: Path) -> None:
    # a method referencing an undefined capability fails the build
    unknown_cap = tmp_path / "unknown_cap.yaml"
    unknown_cap.write_text(
        "capabilities:\n  - {code: cora.capability.x, name: X, executor_shapes: [Method]}\n"
        "methods:\n  - {name: m, capability: cora.capability.missing}\n",
        encoding="utf-8",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(unknown_cap)

    # an empty executor_shapes violates the required-non-empty contract
    empty_shapes = tmp_path / "empty_shapes.yaml"
    empty_shapes.write_text(
        "capabilities:\n  - {code: cora.capability.x, name: X, executor_shapes: []}\n",
        encoding="utf-8",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(empty_shapes)

    # a typo'd field name is rejected (extra=forbid), not silently swallowed
    typo = tmp_path / "typo.yaml"
    typo.write_text(
        "capabilities:\n  - "
        "{code: cora.capability.x, name: X, executor_shapes: [Method], descripton: oops}\n",
        encoding="utf-8",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(typo)


def test_assembly_guards_reject_bad_data(tmp_path: Path) -> None:
    def _write(name: str, body: str) -> Path:
        p = tmp_path / name
        p.write_text(body, encoding="utf-8")
        return p

    # a slot referencing a family the catalog does not define fails the build
    unknown_family = _write(
        "unknown_family.yaml",
        "families:\n  - {name: Camera}\n"
        "assemblies:\n  - name: A\n    required_slots:\n"
        "      - {slot_name: s, required_families: [Ghost], cardinality: Exactly1}\n",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(unknown_family)

    # presents_as referencing an undefined role fails
    unknown_role = _write(
        "unknown_role.yaml",
        "assemblies:\n  - {name: A, presents_as: [Ghost]}\n",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(unknown_role)

    # a sub-assembly link to an undefined Assembly name fails
    unknown_sub = _write(
        "unknown_sub.yaml",
        "assemblies:\n  - name: A\n    required_sub_assemblies:\n"
        "      - {slot_name: x, sub_assembly: Ghost}\n",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(unknown_sub)

    # a wire endpoint naming an undeclared slot fails
    bad_wire = _write(
        "bad_wire.yaml",
        "families:\n  - {name: Camera}\n"
        "assemblies:\n  - name: A\n    required_slots:\n"
        "      - {slot_name: s, required_families: [Camera], cardinality: Exactly1}\n"
        "    required_wires:\n"
        "      - {source_slot: s, source_port: o, target_slot: ghost, target_port: i}\n",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(bad_wire)

    # a wire endpoint naming a sub-assembly LINK position fails: wires close over
    # leaf slots only, matching the spine (WireReferencesUnknownSlotError there)
    wire_to_link = _write(
        "wire_to_link.yaml",
        "families:\n  - {name: Camera}\n"
        "assemblies:\n  - {name: Child}\n  - name: A\n    required_slots:\n"
        "      - {slot_name: cam, required_families: [Camera], cardinality: Exactly1}\n"
        "    required_sub_assemblies:\n      - {slot_name: optics, sub_assembly: Child}\n"
        "    required_wires:\n"
        "      - {source_slot: cam, source_port: o, target_slot: optics, target_port: i}\n",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(wire_to_link)

    # a sub-assembly link slot_name colliding with a leaf slot_name fails
    collision = _write(
        "collision.yaml",
        "families:\n  - {name: Camera}\n"
        "assemblies:\n  - {name: Child}\n  - name: A\n    required_slots:\n"
        "      - {slot_name: dup, required_families: [Camera], cardinality: Exactly1}\n"
        "    required_sub_assemblies:\n      - {slot_name: dup, sub_assembly: Child}\n",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(collision)

    # an unknown cardinality value fails (validated against the mirror)
    bad_cardinality = _write(
        "bad_cardinality.yaml",
        "families:\n  - {name: Camera}\n"
        "assemblies:\n  - name: A\n    required_slots:\n"
        "      - {slot_name: s, required_families: [Camera], cardinality: AtLeast2}\n",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(bad_cardinality)

    # a typo'd assembly field is rejected (extra=forbid)
    typo = _write(
        "assembly_typo.yaml",
        "assemblies:\n  - {name: A, presents_az: [Detector]}\n",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(typo)


def test_malformed_catalog_raises(tmp_path: Path) -> None:
    bad = tmp_path / "catalog.yaml"
    bad.write_text("roles:\n  - docstring: no name here\n", encoding="utf-8")
    with pytest.raises(cd.CatalogError):
        cd.load(bad)

    bad_affordance = tmp_path / "bad_affordance.yaml"
    bad_affordance.write_text(
        "families:\n  - name: X\n    affordances: [NotARealAffordance]\n",
        encoding="utf-8",
    )
    with pytest.raises(cd.CatalogError):
        cd.load(bad_affordance)
