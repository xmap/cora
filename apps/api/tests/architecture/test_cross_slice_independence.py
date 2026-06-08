"""No slice imports from a sibling slice in the same BC.

Vertical slices are independent units. A handler / decider / route
in `cora.<bc>.features.<slice_a>` MUST NOT import from
`cora.<bc>.features.<slice_b>`. Shared types belong in the
aggregate kernel (`cora.<bc>.aggregates.*`); pure cross-BC value
objects belong in `cora.shared`; cross-BC infrastructure with
adapter / port / kernel dependencies belongs in
`cora.infrastructure`.

Tach handles cross-BC rules at module granularity; cross-slice
inside a BC would require ~50 per-slice tach module stanzas, so
we keep that rule here as a single AST scan.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files


def _slice_python_files() -> list[Path]:
    tracked = tracked_python_files()
    out: list[Path] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        out.extend(
            sorted(
                f
                for f in tracked
                if f.parent.parent == features and not f.parent.name.startswith("_")
            )
        )
    return out


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


@pytest.mark.architecture
@pytest.mark.parametrize("py_file", _slice_python_files(), ids=_qualified)
def test_no_cross_slice_imports(py_file: Path) -> None:
    """A slice file may only import from its own slice + aggregate kernel + infra."""
    qualified = _qualified(py_file)
    parts = qualified.split(".")
    # parts: ["cora", "<bc>", "features", "<slice>", "<file>"]
    own_bc = parts[1]
    own_slice_prefix = ".".join(parts[:4])  # "cora.<bc>.features.<slice>"
    sibling_features_prefix = f"cora.{own_bc}.features."

    tree = ast.parse(py_file.read_text())
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        target = node.module
        if not target.startswith(sibling_features_prefix):
            continue
        if target == own_slice_prefix or target.startswith(own_slice_prefix + "."):
            continue
        violations.append(f"line {node.lineno}: from {target} import ...")

    assert not violations, (
        f"{qualified} imports from a sibling slice in the same BC:\n  "
        + "\n  ".join(violations)
        + "\nMove shared types into the aggregate kernel, cora.shared, or cora.infrastructure."
    )
