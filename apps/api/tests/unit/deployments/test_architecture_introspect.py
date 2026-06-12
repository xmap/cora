"""Guards for the Architecture code-introspection generator.

The generator (scripts/architecture_introspect.py) reads the cora source via AST
and is the source the Architecture docs render their factual tables from, so the
tables cannot drift. There is no descriptor to round-trip; the guards here pin
that the introspection agrees with the architecture fitness enumeration and with
an independent filesystem walk, plus the counts the model.md page asserts.

The scripts/ module is loaded via importlib (scripts/ is not on the type-checker's
path); the arch-fitness BCS tuple imports normally.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import BCS

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_CORA = _REPO_ROOT / "apps" / "api" / "src" / "cora"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ai = _load("architecture_introspect")


def _filesystem_aggregates() -> set[tuple[str, str]]:
    """Independent walk: (bc, aggregate) for every aggregates/<name>/ dir that has
    both state.py and events.py and is not underscore-prefixed."""
    pairs: set[tuple[str, str]] = set()
    for bc in BCS:
        agg_root = _CORA / bc / "aggregates"
        if not agg_root.is_dir():
            continue
        for child in agg_root.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if (child / "state.py").is_file() and (child / "events.py").is_file():
                pairs.add((bc, child.name))
    return pairs


def test_introspection_bounded_contexts_match_arch_fitness() -> None:
    model = ai.introspect(_CORA)
    assert {bc.name for bc in model.bcs} == set(BCS)


def test_introspection_aggregates_match_filesystem() -> None:
    model = ai.introspect(_CORA)
    generated = {(bc.name, agg.name) for bc in model.bcs for agg in bc.aggregates}
    assert generated == _filesystem_aggregates()


def test_counts_are_seventeen_bcs_and_forty_aggregates() -> None:
    # Anti-drift pins for the model.md headline; bump deliberately on a BC/aggregate add.
    model = ai.introspect(_CORA)
    assert model.bc_count == 17
    assert model.aggregate_count == 40


def test_enclosure_bc_and_equipment_role_are_present() -> None:
    # The two omissions the audit caught in the hand-authored model.md table.
    model = ai.introspect(_CORA)
    assert model.bc("enclosure").aggregates, "enclosure BC must surface an aggregate"
    assert "role" in {a.name for a in model.bc("equipment").aggregates}


def test_event_union_is_parsed_in_declaration_order() -> None:
    model = ai.introspect(_CORA)
    decision = model.aggregate("decision", "decision")
    names = [e.name for e in decision.events]
    assert names == [
        "DecisionRegistered",
        "DecisionLogbookOpened",
        "DecisionLogbookClosed",
        "DecisionRated",
    ]
    # single-member union (RoleEvent = RoleDefined) parses too
    role = model.aggregate("equipment", "role")
    assert [e.name for e in role.events] == ["RoleDefined"]


def test_slice_surface_extracted_from_route_and_tool() -> None:
    model = ai.introspect(_CORA)
    by_name = {s.dir_name: s for s in model.bc("decision").slices}
    appended = by_name["append_inferences"]
    assert appended.command_class == "AppendInferences"
    assert appended.rest_path == "/decisions/{decision_id}/inferences"
    assert appended.http_method == "POST"
    assert appended.mcp_tool == "append_inferences"


def test_in_process_stub_slice_has_no_surface() -> None:
    model = ai.introspect(_CORA)
    observe = {s.dir_name: s for s in model.bc("supply").slices}["observe_supply_status"]
    assert observe.in_process
    assert observe.rest_path is None and observe.mcp_tool is None
