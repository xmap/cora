"""Pin: a Postgres adapter reads only its OWN BC's projection tables (Anti-hook 2).

The chain-walk landed the first `WITH RECURSIVE` in the codebase
(`PostgresAssetLookup.ancestors_of`). A recursive CTE is exactly the
shape that, left unpoliced, tempts a future edit to JOIN a SECOND BC's
projection into the walk ("while I'm climbing the Asset tree, let me
also pull the Enclosure rows"). That would dissolve the BC seam at the
SQL layer, where tach + import-graph fitness tests cannot see it.

The rule: every Postgres adapter under `cora/<bc>/adapters/` may read
`proj_<bc>_*` tables for its OWN `<bc>` only. Cross-BC integration goes
through a PORT (the consumer shapes it, the owning BC ships the
adapter), never a direct cross-projection SQL read. `ancestors_of`
itself obeys this: it reads `proj_equipment_asset_summary` (+ the
equipment family tables) and joins the Enclosure axis only later, in a
Python handler, via `EnclosureLookup`.

Scope: command-time adapter `.py` files under `cora/*/adapters/`. DDL
migrations are out of scope by design: a migration legitimately defines
or back-fills any table; it is schema authorship, not a command-time
cross-BC read.

The allowlist starts EMPTY and every adapter already obeys. Adding an
entry means a Postgres adapter reads another BC's projection directly,
which is a BC-seam violation absent a design memo overriding the
port-mediated-integration convention.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

# (owning_bc, referenced_bc) pairs permitted to cross. Empty: no
# Postgres adapter may read another BC's projection. Extend only with a
# design memo overriding the port-mediated cross-BC integration rule.
_CROSS_BC_READ_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()

# Captures the BC prefix of a projection table named in a FROM / JOIN
# clause: `FROM proj_equipment_asset_summary` -> "equipment". The
# non-greedy `[a-z]+?` stops at the first underscore (BC names are
# single lowercase tokens), so the multi-word table tail never bleeds
# into the captured BC. `LATERAL`/CTE joins (JOIN ancestors, JOIN
# LATERAL unnest) do not match `proj_` and are ignored.
_PROJ_READ_RE = re.compile(r"\b(?:FROM|JOIN)\s+proj_([a-z]+?)_", re.IGNORECASE)


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _adapter_files() -> list[Path]:
    """Tracked `.py` files under any `cora/<bc>/adapters/` directory."""
    return sorted(p for p in tracked_python_files() if "/adapters/" in str(p))


@pytest.mark.architecture
@pytest.mark.parametrize("path", _adapter_files(), ids=_qualified)
def test_adapter_reads_only_its_own_bc_projection(path: Path) -> None:
    owning_bc = path.relative_to(CORA_ROOT).parts[0]
    text = path.read_text()

    offenders: list[str] = []
    for match in _PROJ_READ_RE.finditer(text):
        referenced_bc = match.group(1).lower()
        if referenced_bc == owning_bc:
            continue
        if (owning_bc, referenced_bc) in _CROSS_BC_READ_ALLOWLIST:
            continue
        lineno = text[: match.start()].count("\n") + 1
        offenders.append(
            f"line {lineno}: reads proj_{referenced_bc}_* (owning BC is {owning_bc!r})"
        )

    assert not offenders, (
        f"{_qualified(path)} reads another BC's projection table(s):\n  "
        + "\n  ".join(offenders)
        + "\n\nA Postgres adapter may read only its OWN BC's proj_<bc>_* "
        "tables. Cross-BC integration goes through a port (the consumer "
        "shapes it, the owning BC ships the adapter), never a direct "
        "cross-projection SQL read. See chain-walk Anti-hook 2. If a "
        "cross-BC read is genuinely justified (requires a design memo), "
        "add the (owning_bc, referenced_bc) pair to "
        "_CROSS_BC_READ_ALLOWLIST in this file with a citation."
    )
