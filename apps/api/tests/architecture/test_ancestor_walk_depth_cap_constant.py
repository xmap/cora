"""Pin: ANCESTOR_WALK_DEPTH_CAP has one definition + exactly two adapter users (Anti-hook 3d).

The depth cap is the belt-and-braces ceiling on the `parent_id` walk
(the load-bearing cycle terminator is each adapter's mechanism: the
Postgres CYCLE clause and the in-memory visited set). For the two
adapters to fail at the SAME depth, the cap must be a SINGLE constant,
not a per-adapter literal that can drift. This pin enforces:

  - exactly one module defines `ANCESTOR_WALK_DEPTH_CAP` (its home is
    the AssetLookup port, the walk contract's natural anchor), and
  - the constant is referenced by EXACTLY the port (definition) plus
    the two AssetLookup adapters, nothing else.

A drift where one adapter inlines `50` while the other imports the
constant would let the two walks disagree on the cap; a third consumer
referencing the cap would mean the limit leaked beyond the two adapters
that own the walk. Either is the failure this guards.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

_CONSTANT = "ANCESTOR_WALK_DEPTH_CAP"

# The one module that DEFINES the cap (the AssetLookup port: the walk
# contract's home).
_DEFINITION_HOME = "cora.infrastructure.ports.asset_lookup"

# Every module permitted to REFERENCE the cap: its definition site plus
# the two AssetLookup adapters that walk the parent_id chain.
_REFERENCE_HOMES: frozenset[str] = frozenset(
    {
        "cora.infrastructure.ports.asset_lookup",
        "cora.infrastructure.adapters.in_memory_asset_lookup",
        "cora.equipment.adapters.postgres_asset_lookup",
    }
)

_DEFINITION_RE = re.compile(rf"^{_CONSTANT}\s*[:=]", re.MULTILINE)
_REFERENCE_RE = re.compile(rf"\b{_CONSTANT}\b")


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


@pytest.mark.architecture
def test_depth_cap_is_defined_in_exactly_one_module() -> None:
    definers = sorted(
        _qualified(p) for p in tracked_python_files() if _DEFINITION_RE.search(p.read_text())
    )
    assert definers == [_DEFINITION_HOME], (
        f"{_CONSTANT} must be defined in exactly one module ({_DEFINITION_HOME}); "
        f"found definitions in {definers}. A second definition lets the two "
        "AssetLookup adapters drift to different caps. See chain-walk Anti-hook 3d."
    )


@pytest.mark.architecture
def test_depth_cap_is_referenced_only_by_the_two_adapters() -> None:
    referrers = sorted(
        _qualified(p) for p in tracked_python_files() if _REFERENCE_RE.search(p.read_text())
    )
    assert set(referrers) == _REFERENCE_HOMES, (
        f"{_CONSTANT} is referenced by {referrers}; expected exactly "
        f"{sorted(_REFERENCE_HOMES)} (the port definition + the two AssetLookup "
        "adapters). A new referrer means the walk's depth limit leaked beyond "
        "the two adapters that own the walk, or an adapter stopped importing "
        "the shared constant. See chain-walk Anti-hook 3d."
    )
