"""Architecture fitness: PIDINST view assembler uses bare aggregate loaders.

Per L6 + L17 of project_asset_persistent_id_design. The view assembler
must compose `AssetPidinstView` via `load_asset` + `load_model` +
`load_family` aggregate-loader replay, NOT via SQL JOINs across
projection tables. This AST-walks the assembler module to:

  1. Confirm the three loader names are imported (composition via
     event-replay).
  2. Reject raw SQL string literals (`SELECT ... FROM ...`, `JOIN`,
     `UPDATE` ...) that would indicate the assembler drifted to a
     SQL-over-summary-tables pattern.

A future v2 projection-backed assembler (D9 of the design memo)
ships under a different module name; pinning the loader-based shape
here keeps the v1 closure-proof contract intact.
"""

import ast
import re

import pytest

from tests.architecture.conftest import CORA_ROOT

pytestmark = [pytest.mark.architecture]


_ASSEMBLER_PATH = CORA_ROOT / "equipment" / "features" / "get_asset_pidinst" / "_view_assembler.py"
_REQUIRED_LOADERS = frozenset({"load_asset", "load_model", "load_family"})
_FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(SELECT\s|UPDATE\s|INSERT\s|DELETE\s|JOIN\s|FROM\s+proj_)",
    re.IGNORECASE,
)


def test_get_asset_pidinst_assembler_imports_aggregate_loaders() -> None:
    """The assembler imports `load_asset` + `load_model` + `load_family`."""
    tree = ast.parse(_ASSEMBLER_PATH.read_text())
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.name)
    missing = _REQUIRED_LOADERS - imported_names
    assert not missing, (
        "_view_assembler.py must import "
        f"{sorted(_REQUIRED_LOADERS)} per the L6 read-via-event-replay "
        f"contract; missing: {sorted(missing)}"
    )


def test_get_asset_pidinst_assembler_contains_no_raw_sql_strings() -> None:
    """The assembler must contain no SQL string literals (no SELECT /
    UPDATE / INSERT / DELETE / JOIN / FROM proj_*). v1 ships as
    event-stream replay; SQL-over-summary-tables ships as a separate v2
    projection-backed assembler (D9) under a different name."""
    tree = ast.parse(_ASSEMBLER_PATH.read_text())
    violations: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _FORBIDDEN_SQL_PATTERN.search(node.value)
        ):
            violations.append(
                f"line {node.lineno}: SQL pattern in string literal: {node.value[:60]!r}"
            )
    assert not violations, (
        "_view_assembler.py must contain no raw SQL strings per L6 + L17:\n  "
        + "\n  ".join(violations)
    )
