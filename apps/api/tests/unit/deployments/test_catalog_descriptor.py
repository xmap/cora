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


def _vals(items: Any) -> set[str]:
    """Stringify a collection of enums / VOs / strings to a comparable set."""
    return {str(getattr(x, "value", x)) for x in items}


def test_catalog_loads_and_validates() -> None:
    cat = cd.load(_CATALOG)
    assert len(cat.roles) == 4
    assert {r.name for r in cat.roles} == {"Imager", "Positioner", "Controller", "Detector"}
    assert len(cat.families) >= 10
    assert len(cat.capabilities) == 5
    assert len(cat.methods) == 15
    assert len(cat.models) >= 12
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
