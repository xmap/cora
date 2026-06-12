"""Pin: the recursive ancestor walk lives ONLY in the equipment Asset adapter (Anti-hook 2).

`ancestors_of` is the ONE place a `parent_id` chain is walked in SQL.
Its recursive CTE (`WITH RECURSIVE`) is the first and, by this pin, the
only one in the codebase. Confining it to
`cora/equipment/adapters/postgres_asset_lookup.py` is load-bearing:

  - A recursive CTE anywhere else is almost always a handler or a
    sibling BC trying to re-derive the Asset hierarchy itself, instead
    of calling `AssetLookup.ancestors_of`. That re-opens the H1
    handler-walks-the-tree anti-pattern the H3 design rejected.
  - It keeps cycle-defense (the SQL-standard CYCLE clause + the depth
    cap) in a SINGLE reviewed implementation. A second hand-rolled
    recursive walk would be a second place to get cycle termination
    wrong.

This pin keys on `WITH RECURSIVE`, NOT on the token `parent_id`: the
one-hop `parent_id` reads that already exist (for example a snapshot
column select, or a controller_id-style single union) are legitimate
and must not trip. Only a RECURSIVE walk is constrained here.

If you are here because this failed, you almost certainly want to call
`AssetLookup.ancestors_of` (or add a sibling walk method on that port),
not hand-roll a second recursive CTE.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

# The sole module permitted to contain a `WITH RECURSIVE` walk. The
# ancestor closure (and any future descendants_of mirror) lives behind
# the AssetLookup port's equipment adapter.
_RECURSIVE_WALK_HOME = "cora.equipment.adapters.postgres_asset_lookup"

_WITH_RECURSIVE_RE = re.compile(r"\bwith\s+recursive\b", re.IGNORECASE)


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


@pytest.mark.architecture
def test_with_recursive_lives_only_in_the_equipment_asset_adapter() -> None:
    offenders: list[str] = []
    for path in sorted(tracked_python_files()):
        qualified = _qualified(path)
        if qualified == _RECURSIVE_WALK_HOME:
            continue
        if _WITH_RECURSIVE_RE.search(path.read_text()):
            offenders.append(qualified)

    assert not offenders, (
        "WITH RECURSIVE appears outside the one permitted module "
        f"({_RECURSIVE_WALK_HOME}):\n  " + "\n  ".join(offenders) + "\n\n"
        "The recursive parent_id walk belongs behind the AssetLookup "
        "port's equipment adapter (ancestors_of), so cycle-defense lives "
        "in a single reviewed place and handlers cannot re-derive the "
        "Asset hierarchy themselves. Call AssetLookup.ancestors_of (or "
        "add a sibling walk method on that port) instead of hand-rolling "
        "a recursive CTE. See chain-walk Anti-hook 2."
    )


@pytest.mark.architecture
def test_equipment_asset_adapter_actually_has_the_recursive_walk() -> None:
    """Guard against the pin silently passing if the walk is deleted/moved.

    A location pin that asserts "only here" is vacuously true if the
    walk vanishes from `here` too. Anchor it: the home module must
    actually contain the recursive walk.
    """
    home = CORA_ROOT / "equipment" / "adapters" / "postgres_asset_lookup.py"
    assert _WITH_RECURSIVE_RE.search(home.read_text()), (
        f"{_RECURSIVE_WALK_HOME} no longer contains a WITH RECURSIVE walk. "
        "If ancestors_of moved, update _RECURSIVE_WALK_HOME in this test."
    )
