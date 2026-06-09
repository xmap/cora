"""Scenario metadata parser, closed vocabularies, and directory scanner.

Used by two consumers:

  1. apps/api/tests/integration/scenarios/conftest.py validates every
     scenario file's module docstring at pytest collection time. A
     missing header or invalid vocabulary value fails the test session
     with a precise file + reason error.

  2. scripts/mkdocs_hooks.py reads the same headers at docs build
     time and generates the docs/scenarios/ surface (cluster pages,
     axis indexes, per-scenario stubs).

Single source of truth for the closed vocabularies; mirrored in
apps/api/tests/integration/scenarios/README.md prose and in
project_scenario_taxonomy.md memory.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

CLUSTERS: frozenset[str] = frozenset(
    {"Seed", "Commissioning", "Staging", "Runs", "Advisories"}
)

ARCHETYPES: frozenset[str] = frozenset(
    {
        "setup",
        "routine",
        "cycle",
        "fsm",
        "gate",
        "agent",
    }
)

# All 17 BCs that exist in CORA's codebase today. New BCs are added
# at ship time, not when first scenario covers them, so a zero-count
# BC on the registry page is a visible signal of a coverage gap.
BOUNDED_CONTEXTS: frozenset[str] = frozenset(
    {
        "Access",
        "Trust",
        "Federation",
        "Equipment",
        "Recipe",
        "Subject",
        "Run",
        "Campaign",
        "Data",
        "Decision",
        "Supply",
        "Operation",
        "Safety",
        "Caution",
        "Agent",
        "Calibration",
        "Enclosure",
    }
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "cluster",
    "archetype",
    "bc_primary",
    "bc_touches",
)


@dataclass(frozen=True)
class ScenarioMeta:
    """Parsed metadata for one scenario test file."""

    stem: str  # filename without .py, eg "test_2bm_tomography_scan"
    gist: str  # first line of the module docstring
    cluster: str
    archetype: str
    bc_primary: str
    bc_touches: tuple[str, ...]  # sorted, deduped


class ScenarioHeaderError(ValueError):
    """Raised when a scenario file's docstring header is missing or invalid."""


_FIELD_RE = re.compile(r"^(\w+):\s*(.+?)\s*$")


def parse_metadata(path: Path, docstring: str | None) -> ScenarioMeta:
    """Parse the gist + metadata block from a scenario module docstring.

    Raises ScenarioHeaderError with a clear message on any problem.
    """
    if docstring is None:
        raise ScenarioHeaderError(f"{path}: missing module docstring")
    lines = docstring.split("\n")
    if not lines or not lines[0].strip():
        raise ScenarioHeaderError(f"{path}: first line of docstring must be the gist")
    gist = lines[0].strip()

    # Find the metadata block: contiguous key:value lines after the
    # first blank line.
    i = 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    block_start = i
    while i < len(lines) and lines[i].strip() != "":
        i += 1
    block_lines = lines[block_start:i]

    fields: dict[str, str] = {}
    for raw in block_lines:
        m = _FIELD_RE.match(raw)
        if not m:
            raise ScenarioHeaderError(
                f"{path}: malformed metadata line {raw!r} (expected `key: value`)"
            )
        fields[m.group(1)] = m.group(2)

    missing = [f for f in REQUIRED_FIELDS if f not in fields]
    if missing:
        raise ScenarioHeaderError(
            f"{path}: docstring header missing required field(s): {', '.join(missing)}"
        )

    cluster = fields["cluster"]
    if cluster not in CLUSTERS:
        raise ScenarioHeaderError(
            f"{path}: cluster {cluster!r} not in closed vocabulary ({sorted(CLUSTERS)})"
        )

    archetype = fields["archetype"]
    if archetype not in ARCHETYPES:
        raise ScenarioHeaderError(
            f"{path}: archetype {archetype!r} not in closed vocabulary "
            f"({sorted(ARCHETYPES)})"
        )

    bc_primary = fields["bc_primary"]
    if bc_primary not in BOUNDED_CONTEXTS:
        raise ScenarioHeaderError(
            f"{path}: bc_primary {bc_primary!r} not in closed vocabulary "
            f"({sorted(BOUNDED_CONTEXTS)})"
        )

    touches_raw = [t.strip() for t in fields["bc_touches"].split(",") if t.strip()]
    bad = [t for t in touches_raw if t not in BOUNDED_CONTEXTS]
    if bad:
        raise ScenarioHeaderError(
            f"{path}: bc_touches contains unknown BC(s) {bad} "
            f"(closed vocabulary: {sorted(BOUNDED_CONTEXTS)})"
        )
    if bc_primary not in touches_raw:
        raise ScenarioHeaderError(
            f"{path}: bc_primary {bc_primary!r} must also appear in bc_touches"
        )

    return ScenarioMeta(
        stem=path.stem,
        gist=gist,
        cluster=cluster,
        archetype=archetype,
        bc_primary=bc_primary,
        bc_touches=tuple(sorted(set(touches_raw))),
    )


def extract_docstring(path: Path) -> str | None:
    """Pure-AST module-docstring extraction (no imports, no execution)."""
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as exc:
        raise ScenarioHeaderError(f"{path}: syntax error: {exc}") from exc
    return ast.get_docstring(tree)


def scan_dir(scenarios_dir: Path) -> list[ScenarioMeta]:
    """Return parsed metadata for every test_*.py in scenarios_dir.

    Raises ScenarioHeaderError on the first invalid file (fail-fast).
    """
    metas: list[ScenarioMeta] = []
    for path in sorted(scenarios_dir.glob("test_*.py")):
        doc = extract_docstring(path)
        metas.append(parse_metadata(path, doc))
    return metas


__all__ = [
    "ARCHETYPES",
    "BOUNDED_CONTEXTS",
    "CLUSTERS",
    "REQUIRED_FIELDS",
    "ScenarioHeaderError",
    "ScenarioMeta",
    "extract_docstring",
    "parse_metadata",
    "scan_dir",
]
