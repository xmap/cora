"""Domain error classes live in the aggregate kernel, not in slices.

Per ``docs/reference/patterns.md`` Rejections table:

  - Validation / NotFound / AlreadyExists / state-transition errors
    live in ``cora/<bc>/aggregates/<aggregate>/state.py`` (or an
    aggregate-internal VO module beside it).
  - BC-application errors (``UnauthorizedError`` and BC-scoped
    cross-aggregate guards) live in ``cora/<bc>/errors.py``.
  - Cross-BC infra errors live under ``cora/infrastructure/`` or
    ``cora/shared/`` (pure value-object construction errors).

Errors defined inside a slice (``features/<slice>/*.py``), a projection
module, a subscriber, an adapter, or a prompt template are out of contract.
The slice-shape fitness wouldn't notice; the routes-completeness fitness
walks ``aggregates.__all__`` and BC ``__all__`` and would silently miss
any error not re-exported through those.

Private classes (leading underscore) are exempt: they're tool-local
validation helpers (``_ListCautionsInputError`` etc.) that never reach
the HTTP / MCP contract.

``WIP_SLICE_ERRORS`` is an explicit allowlist for slice-local errors
that are mid-renovation. Each entry MUST cite the finding and the phase
that will close it.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


# Each entry is "qualified_module:ClassName".
WIP_SLICE_ERRORS: frozenset[str] = frozenset()


def _is_exempt_path(path: Path) -> bool:
    """Locations where Error classes are documented to live."""
    parts = path.relative_to(CORA_ROOT).parts
    # cora/<bc>/aggregates/...
    if len(parts) >= 2 and parts[1] == "aggregates":
        return True
    # cora/<bc>/errors.py
    if len(parts) == 2 and parts[1] == "errors.py":
        return True
    # cora/<bc>/ports/... mirrors cora/infrastructure/ports/...: port-tier
    # exception classes (wire-protocol errors caught by the executor's
    # decider per project_non_determinism_principle) co-locate with the
    # Protocol they belong to; first instance is ControlPort.
    if len(parts) >= 2 and parts[1] == "ports":
        return True
    # cora/infrastructure/... and cora/shared/...
    return bool(parts and parts[0] in {"infrastructure", "shared"})


def _scanned_files() -> list[Path]:
    return sorted(p for p in tracked_python_files() if not _is_exempt_path(p))


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _public_error_classes(tree: ast.Module) -> list[tuple[int, str]]:
    """Top-level ``class Foo*Error(...)`` defs without a leading underscore."""
    out: list[tuple[int, str]] = []
    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name.endswith("Error")
            and not node.name.startswith("_")
        ):
            out.append((node.lineno, node.name))
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("path", _scanned_files(), ids=_qualified)
def test_no_domain_errors_outside_aggregate_or_errors_module(path: Path) -> None:
    qualified = _qualified(path)
    tree = ast.parse(path.read_text())
    violations: list[str] = []
    for lineno, cls in _public_error_classes(tree):
        key = f"{qualified}:{cls}"
        if key in WIP_SLICE_ERRORS:
            continue
        violations.append(f"line {lineno}: {cls}")
    assert not violations, (
        f"{qualified} defines domain error(s) outside the aggregate "
        f"kernel:\n  " + "\n  ".join(violations) + "\n"
        "Move them to cora/<bc>/aggregates/<aggregate>/state.py (domain) "
        "or cora/<bc>/errors.py (BC-application) per "
        "docs/reference/patterns.md Rejections."
    )


@pytest.mark.architecture
def test_wip_slice_errors_actually_exist() -> None:
    """``WIP_SLICE_ERRORS`` entries must point at real class defs."""
    for entry in WIP_SLICE_ERRORS:
        qualified, _, cls = entry.partition(":")
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{entry}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:]).with_suffix(".py")
        assert path.is_file(), f"WIP_SLICE_ERRORS entry {entry}: file missing"
        tree = ast.parse(path.read_text())
        names = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
        assert cls in names, (
            f"WIP_SLICE_ERRORS entry {entry}: class no longer defined in that file; remove it"
        )
