"""Tests for the catalog:* marker expander.

Deployment pages show curated subsets of the cross-facility catalog (the vendor
Models their hardware binds). The catalog:models marker renders those tables from
catalog/catalog.yaml (manufacturer, part number, families) and, for the used-by
column, from the beamline descriptor, so the part numbers cannot drift. This test
loads both descriptors and the expander through the same scripts/ modules the
mkdocs on_page_markdown hook uses.

The scripts/ modules are loaded via importlib (the dynamic-import bridge used by
tests/integration/scenarios/conftest.py), since scripts/ is not on the
type-checker's path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_DESCRIPTOR = _REPO_ROOT / "deployments" / "2-bm" / "beamline.yaml"
_CATALOG = _REPO_ROOT / "catalog" / "catalog.yaml"
_MICROSCOPE_PAGE = _REPO_ROOT / "docs" / "deployments" / "2-bm" / "equipment" / "microscope.md"
_MICROSCOPE_SRC_URI = "deployments/2-bm/equipment/microscope.md"
_INVENTORY_PAGE = _REPO_ROOT / "docs" / "deployments" / "2-bm" / "inventory.md"
_INVENTORY_SRC_URI = "deployments/2-bm/inventory.md"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bd = _load("beamline_descriptor")
cd = _load("catalog_descriptor")
cm = _load("catalog_markers")


def _catalog() -> object:
    return cd.load(_CATALOG)


def _descriptor() -> object:
    return bd.load(_DESCRIPTOR)


def test_models_marker_families_renders_manufacturer_part_and_families() -> None:
    rendered = cm.render_models(
        _catalog(), _descriptor(), {"models": "flir_oryx,crytur_luag", "show": "families"}
    )
    assert "FLIR" in rendered
    assert "`ORX-10G-51S5M-C`" in rendered
    assert "`Scintillator`" in rendered
    assert "Declared families" in rendered


def test_models_marker_usedby_derives_binding_assets_from_descriptor() -> None:
    rendered = cm.render_models(
        _catalog(), _descriptor(), {"models": "oms_vme58", "show": "usedby"}
    )
    # oms_vme58 is bound by both OMS crates; the used-by column inverts the
    # device.model field across groups and controllers.
    assert "`SampleStageDrive`" in rendered
    assert "`FrontEndDrive`" in rendered
    assert "Used by" in rendered


def test_models_marker_unknown_model_raises() -> None:
    with pytest.raises(cm.CatalogMarkerError):
        cm.render_models(_catalog(), _descriptor(), {"models": "no_such_model"})


def test_models_marker_unknown_show_raises() -> None:
    with pytest.raises(cm.CatalogMarkerError):
        cm.render_models(_catalog(), _descriptor(), {"models": "oms_vme58", "show": "nonsense"})


def test_microscope_page_uses_catalog_marker_and_expands() -> None:
    source = _MICROSCOPE_PAGE.read_text(encoding="utf-8")
    assert "<!-- catalog:models" in source
    expanded = cm.expand_markers(
        source, catalog=_catalog(), descriptor=_descriptor(), src_uri=_MICROSCOPE_SRC_URI
    )
    assert "| Model | Manufacturer | Part number | Declared families |" in expanded
    assert "`MICRX080`" in expanded
    # The vendor table carries the "edit the catalog, not this table" note.
    assert '!!! info "Generated from the catalog"' in expanded
    assert "catalog/catalog.yaml" in expanded


def test_inventory_page_uses_catalog_marker_and_expands() -> None:
    source = _INVENTORY_PAGE.read_text(encoding="utf-8")
    assert "<!-- catalog:models" in source
    expanded = cm.expand_markers(
        source, catalog=_catalog(), descriptor=_descriptor(), src_uri=_INVENTORY_SRC_URI
    )
    assert "| Model | Manufacturer | Part number | Used by |" in expanded
    assert "`SampleTop_X`" in expanded


def test_unpaired_marker_raises() -> None:
    markdown = "<!-- catalog:models models=oms_vme58 -->\nno closing marker"
    with pytest.raises(cm.CatalogMarkerError):
        cm.expand_markers(
            markdown, catalog=_catalog(), descriptor=_descriptor(), src_uri="deployments/2-bm/x.md"
        )
