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
_DOCS_ARCH = _REPO_ROOT / "docs" / "architecture"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {_SCRIPTS_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ai = _load("architecture_introspect")
ap = _load("architecture_pages")
_MODEL = ai.introspect(_CORA)


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


def test_bc_table_renders_full_membership() -> None:
    table = ap.render_bc_table(_MODEL, {})
    assert "`enclosure`" in table  # the omitted 17th BC
    assert "`role`" in table  # the omitted equipment aggregate
    assert table.count("Active") == 17
    assert table.count("Planned") == 2
    assert "`strategy`" in table and "`budget`" in table
    assert chr(0x2014) not in table


def test_bc_table_group_map_covers_every_bc() -> None:
    # The editorial group map must place every introspected BC, else a new BC is
    # silently dropped from the table. render_bc_table also raises on a gap.
    placed = {bc for _, bc in ap._BC_ROWS} | {bc for _, bc, _ in ap._PLANNED_ROWS}
    assert {bc.name for bc in _MODEL.bcs} - placed == set()


def test_count_renderer() -> None:
    assert ap.render_count(_MODEL, {"kind": "bc", "spell": "true", "cap": "true"}) == "Seventeen"
    assert ap.render_count(_MODEL, {"kind": "aggregate", "spell": "true"}) == "forty"
    assert ap.render_count(_MODEL, {"kind": "bc"}) == "17"
    assert ap.render_count(_MODEL, {"kind": "event", "bc": "decision"}) == "4"
    assert ap.render_count(_MODEL, {"kind": "slice", "bc": "equipment"}) == "60"


def test_decision_slices_table_uses_real_surface() -> None:
    # The audit's high finding: the decision page documented a nonexistent
    # append_reasoning_entry tool/REST. The generated table uses the real surface.
    table = ap.render_slices_table(_MODEL, {"bc": "decision"})
    assert "`AppendInferences`" in table
    assert "/decisions/{decision_id}/inferences" in table
    assert "`append_inferences`" in table
    assert "append_reasoning_entry" not in table
    assert "AppendReasoningEntry" not in table


def test_bc_aggregates_renderer() -> None:
    aggs = ap.render_bc_aggregates(_MODEL, {"bc": "equipment"})
    assert "`role`" in aggs and "`asset`" in aggs
    # case=type emits the PascalCase aggregate type names (for the index cards)
    typed = ap.render_bc_aggregates(_MODEL, {"bc": "equipment", "case": "type"})
    assert "`Role`" in typed and "`Asset`" in typed and "`role`" not in typed


def test_expand_markers_idempotent() -> None:
    md = "lead <!-- arch:count kind=bc spell=true cap=true -->X<!-- /arch:count --> tail"
    out = ap.expand_markers(md, model=_MODEL, src_uri="architecture/model.md")
    assert "Seventeen" in out
    assert out.startswith("lead <!-- arch:count") and out.endswith("/arch:count --> tail")
    # re-expanding a generated page is stable
    assert ap.expand_markers(out, model=_MODEL, src_uri="architecture/model.md") == out


def test_every_architecture_marker_expands_cleanly() -> None:
    # Walk the real docs: every arch:* marker on every architecture/ page must
    # expand against the live model without raising (no stale bc/agg, no bad arg).
    md_files = sorted(_DOCS_ARCH.rglob("*.md"))
    assert md_files, "expected architecture docs pages"
    seen_marker = False
    for path in md_files:
        text = path.read_text(encoding="utf-8")
        if "<!-- arch:" not in text:
            continue
        seen_marker = True
        src_uri = f"architecture/{path.relative_to(_DOCS_ARCH).as_posix()}"
        out = ap.expand_markers(text, model=_MODEL, src_uri=src_uri)
        assert "<!-- arch:" in out  # markers are preserved for the next build
        assert chr(0x2014) not in out, f"{src_uri} has an em dash"
    assert seen_marker, "no architecture page carries an arch:* marker"


def test_model_md_has_exactly_one_bc_table() -> None:
    text = (_DOCS_ARCH / "model.md").read_text(encoding="utf-8")
    assert text.count("<!-- arch:bc-table -->") == 1


def test_expand_markers_rejects_bad_markers() -> None:
    cases = [
        "<!-- arch:bogus -->x<!-- /arch:bogus -->",  # unknown kind
        "<!-- arch:count -->x<!-- /arch:count -->",  # missing required kind arg
        "<!-- arch:count kind=bc nope=1 -->x<!-- /arch:count -->",  # unknown arg
        "<!-- arch:bc-table -->x",  # unpaired (no close)
    ]
    for md in cases:
        with pytest.raises(ap.ArchMarkerError):
            ap.expand_markers(md, model=_MODEL, src_uri="architecture/x.md")
