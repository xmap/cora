"""Pin the AssetLevel.ASSEMBLY -> AssetLevel.COMPONENT rename.

The token `Assembly` was freed for the new Assembly aggregate in
Equipment BC (5th aggregate, designed in
[[project_assembly_aggregate_design]]). Re-introducing
`AssetLevel.ASSEMBLY` as a symbolic reference, or `"Assembly"` as a
string literal in a context that means the level value, would
collide with the new aggregate's name and break the rename.

This fitness catches three regressions:

1. Any symbolic reference to `AssetLevel.ASSEMBLY` under `src/cora`.
2. The same symbolic reference under `tests/`.
3. The bare `"Assembly"` / `'Assembly'` string literal anywhere
   under `src/cora` or `tests/`, with a narrow allow-list. Catches
   the level value leaking into Literal types, JSON-Schema enums,
   MCP tool descriptions, route descriptions, contract docstrings,
   or event-payload fixtures.

All three checks scope to tracked files via `tracked_python_files()`
and `tracked_test_files()`, per the conftest convention.

The membership of the `AssetLevel` enum itself is pinned in
`tests/unit/equipment/test_asset.py`
(`test_asset_level_has_all_six_isa88_levels`); this fitness adds
the symbolic and literal sweeps.
"""

from pathlib import Path

import pytest

from tests.architecture.conftest import (
    tracked_python_files,
    tracked_test_files,
)

_SYMBOLIC_REFERENCE = "AssetLevel.ASSEMBLY"

# Files allowed to contain the bare "Assembly" / 'Assembly' literal.
# Today the only legitimate carrier is this fitness file itself (the
# docstring and the patterns variable both reference the literal).
# When Sub-Stage B ships the Assembly aggregate, that aggregate's
# state.py / events.py / projector / slices each become candidates
# for this allow-list. Add them one at a time at gate review.
_ALLOW_RELATIVE_PATHS: frozenset[str] = frozenset(
    {
        "apps/api/tests/architecture/test_no_assembly_asset_level_literal.py",
        # The Assembly aggregate legitimately carries the "Assembly"
        # token in event_type discriminators (`case "AssemblyDefined":`),
        # docstrings, and class names. Added at v1 ship of the
        # aggregate; widen the list as new sites land at gate review.
        "apps/api/src/cora/equipment/_template_slot_body.py",
        "apps/api/src/cora/equipment/_template_wire_body.py",
        "apps/api/src/cora/equipment/aggregates/assembly/_content_hash.py",
        "apps/api/src/cora/equipment/aggregates/assembly/__init__.py",
        "apps/api/src/cora/equipment/aggregates/assembly/events.py",
        "apps/api/src/cora/equipment/aggregates/assembly/evolver.py",
        "apps/api/src/cora/equipment/aggregates/assembly/read.py",
        "apps/api/src/cora/equipment/aggregates/assembly/state.py",
        "apps/api/src/cora/equipment/features/define_assembly/__init__.py",
        "apps/api/src/cora/equipment/features/define_assembly/command.py",
        "apps/api/src/cora/equipment/features/define_assembly/context.py",
        "apps/api/src/cora/equipment/features/define_assembly/decider.py",
        "apps/api/src/cora/equipment/features/define_assembly/handler.py",
        "apps/api/src/cora/equipment/features/define_assembly/route.py",
        "apps/api/src/cora/equipment/features/define_assembly/tool.py",
        "apps/api/src/cora/equipment/features/deprecate_assembly/__init__.py",
        "apps/api/src/cora/equipment/features/deprecate_assembly/command.py",
        "apps/api/src/cora/equipment/features/deprecate_assembly/decider.py",
        "apps/api/src/cora/equipment/features/deprecate_assembly/handler.py",
        "apps/api/src/cora/equipment/features/deprecate_assembly/route.py",
        "apps/api/src/cora/equipment/features/deprecate_assembly/tool.py",
        "apps/api/src/cora/equipment/features/version_assembly/__init__.py",
        "apps/api/src/cora/equipment/features/version_assembly/command.py",
        "apps/api/src/cora/equipment/features/version_assembly/context.py",
        "apps/api/src/cora/equipment/features/version_assembly/decider.py",
        "apps/api/src/cora/equipment/features/version_assembly/handler.py",
        "apps/api/src/cora/equipment/features/version_assembly/route.py",
        "apps/api/src/cora/equipment/features/version_assembly/tool.py",
        "apps/api/src/cora/equipment/projections/assembly_summary.py",
        "apps/api/tests/contract/test_assemblies_endpoint.py",
        "apps/api/tests/contract/test_assembly_deprecate_endpoint.py",
        "apps/api/tests/contract/test_assembly_versions_endpoint.py",
        "apps/api/tests/contract/test_define_assembly_mcp_tool.py",
        "apps/api/tests/contract/test_deprecate_assembly_mcp_tool.py",
        "apps/api/tests/contract/test_version_assembly_mcp_tool.py",
        "apps/api/tests/integration/test_define_assembly_handler_postgres.py",
        "apps/api/tests/integration/test_deprecate_assembly_handler_postgres.py",
        "apps/api/tests/integration/test_register_fixture_handler_postgres.py",
        "apps/api/tests/integration/test_version_assembly_handler_postgres.py",
        "apps/api/tests/unit/equipment/test_define_assembly_decider_properties.py",
        "apps/api/tests/unit/equipment/test_deprecate_assembly_decider.py",
        "apps/api/tests/unit/equipment/test_deprecate_assembly_decider_properties.py",
        "apps/api/tests/unit/equipment/test_version_assembly_decider.py",
        "apps/api/tests/unit/equipment/test_version_assembly_decider_properties.py",
        "apps/api/tests/unit/equipment/test_assembly_content_hash.py",
        "apps/api/tests/unit/equipment/test_assembly_events.py",
        "apps/api/tests/unit/equipment/test_assembly_evolver.py",
        "apps/api/tests/unit/equipment/test_assembly_state.py",
        "apps/api/tests/unit/equipment/test_assembly_summary_projection.py",
        "apps/api/tests/unit/equipment/test_assembly_template_slot.py",
        "apps/api/tests/unit/equipment/test_assembly_template_wire.py",
        "apps/api/tests/unit/equipment/test_define_assembly_decider.py",
    }
)

_LITERAL_PATTERNS: tuple[str, ...] = ('"Assembly"', "'Assembly'")


def _scan(
    paths: frozenset[Path],
    needle: str,
    repo_root: Path,
) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in paths:
        try:
            relative = path.relative_to(repo_root).as_posix()
        except ValueError:
            relative = path.as_posix()
        if relative in _ALLOW_RELATIVE_PATHS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if needle in line:
                hits.append((path, line_no, line.strip()))
    return hits


def _scan_literals_with_allow_list(
    paths: frozenset[Path],
    repo_root: Path,
) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in paths:
        try:
            relative = path.relative_to(repo_root).as_posix()
        except ValueError:
            relative = path.as_posix()
        if relative in _ALLOW_RELATIVE_PATHS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if any(pattern in line for pattern in _LITERAL_PATTERNS):
                hits.append((path, line_no, line.strip()))
    return hits


@pytest.mark.architecture
def test_no_asset_level_assembly_symbolic_reference_in_source() -> None:
    """`AssetLevel.ASSEMBLY` must not appear anywhere under src/cora.

    The enum value was renamed to `AssetLevel.COMPONENT`; any
    surviving symbolic reference would fail to import and signals a
    bad merge. The fitness file itself is allow-listed because its
    docstring names the renamed token by design.
    """
    repo_root = Path(__file__).resolve().parents[4]
    hits = _scan(tracked_python_files(), _SYMBOLIC_REFERENCE, repo_root)
    assert hits == [], (
        f"Found {len(hits)} reference(s) to {_SYMBOLIC_REFERENCE} under "
        f"src/cora; rename to AssetLevel.COMPONENT.\n"
        + "\n".join(f"  {p}:{n}: {line}" for p, n, line in hits)
    )


@pytest.mark.architecture
def test_no_asset_level_assembly_symbolic_reference_in_tests() -> None:
    """Same sweep over tests/. Tests are tracked separately because
    pre-commit handles them via a different stash window. The fitness
    file itself is allow-listed."""
    repo_root = Path(__file__).resolve().parents[4]
    hits = _scan(tracked_test_files(), _SYMBOLIC_REFERENCE, repo_root)
    assert hits == [], (
        f"Found {len(hits)} reference(s) to {_SYMBOLIC_REFERENCE} under "
        f"tests/; rename to AssetLevel.COMPONENT.\n"
        + "\n".join(f"  {p}:{n}: {line}" for p, n, line in hits)
    )


@pytest.mark.architecture
def test_no_assembly_string_literal_in_tracked_python() -> None:
    """The bare `"Assembly"` / `'Assembly'` literal must not appear in
    any tracked Python source or test file, except those on the
    narrow allow-list. Catches the level value leaking into Literal
    types, JSON-Schema enums, MCP tool descriptions, route
    descriptions, contract docstrings, or event-payload fixtures.

    Allow-list candidates expand as Sub-Stage B and beyond add
    legitimate carriers of the Assembly aggregate name; add at gate
    review time, not preemptively.
    """
    repo_root = Path(__file__).resolve().parents[4]
    all_paths: frozenset[Path] = tracked_python_files() | tracked_test_files()
    hits = _scan_literals_with_allow_list(all_paths, repo_root)
    assert hits == [], (
        f"Found {len(hits)} bare 'Assembly' literal(s) outside the "
        f"allow-list; rename to 'Component' or widen the allow-list at "
        f"gate review.\n" + "\n".join(f"  {p}:{n}: {line}" for p, n, line in hits)
    )
