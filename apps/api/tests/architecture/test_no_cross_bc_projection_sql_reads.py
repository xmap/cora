"""Pin: BC source reads only its OWN BC's projection tables (Anti-hook 2).

The chain-walk landed the first `WITH RECURSIVE` in the codebase
(`PostgresAssetLookup.ancestors_of`). A recursive CTE is exactly the
shape that, left unpoliced, tempts a future edit to JOIN a SECOND BC's
projection into the walk ("while I'm climbing the Asset tree, let me
also pull the Enclosure rows"). That would dissolve the BC seam at the
SQL layer, where tach + import-graph fitness tests cannot see it.

The rule: every BC's source may read `proj_<bc>_*` tables for its OWN
`<bc>` only. Cross-BC integration goes through a PORT (the consumer
shapes it, the owning BC ships the adapter), never a direct
cross-projection SQL read. `ancestors_of` itself obeys this: it reads
`proj_equipment_asset_summary` (+ the equipment family tables) and joins
the Enclosure axis only later, in a Python handler, via
`EnclosureLookup`.

Scope: every tracked `.py` file under `src/cora`, not just
`cora/*/adapters/`. The original adapter-only scope had a blind spot: a
cross-BC projection read can live in a lifespan/bootstrap file at the BC
root just as easily as in an adapter. The Data BC default-storage-supply
bootstrap (`cora/data/_bootstrap.py`) read `proj_supply_summary`
directly until it moved onto `SupplyLookup.find_supply_by_name`; an
adapter-scoped pin never saw it. DDL migrations are `.sql`, not in this
set, and remain out of scope by design: a migration legitimately defines
or back-fills any table; it is schema authorship, not a command-time
cross-BC read.

The allowlist starts EMPTY and every BC source file already obeys.
Adding an entry means a BC reads another BC's projection directly, which
is a BC-seam violation absent a design memo overriding the
port-mediated-integration convention.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

# (owning_bc, referenced_bc) pairs permitted to cross. Empty: no BC
# source file may read another BC's projection. Extend only with a
# design memo overriding the port-mediated cross-BC integration rule.
_CROSS_BC_READ_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()

# Aggregate-named tables whose first token is NOT the owning BC:
# full table name -> owning BC. Without this, the prefix-derived
# ownership below misreads `proj_language_model_summary` as a read of
# a (nonexistent) `language` BC. Reads of a listed table from any
# OTHER BC still fail the rule.
_TABLE_OWNER_OVERRIDES: dict[str, str] = {
    # agent BC's LanguageModel aggregate keeps the aggregate-named
    # shape (equipment owns the `Model` stream type; see the
    # model-catalog design lock and test_projection_table_bc_prefix).
    "proj_language_model_summary": "agent",
}

# Captures the full projection table named in a FROM / JOIN clause:
# `FROM proj_equipment_asset_summary` -> "proj_equipment_asset_summary".
# The owning BC is then the table's first token (BC names are single
# lowercase tokens) unless `_TABLE_OWNER_OVERRIDES` names the table
# explicitly. `LATERAL`/CTE joins (JOIN ancestors, JOIN LATERAL
# unnest) do not match `proj_` and are ignored.
_PROJ_READ_RE = re.compile(r"\b(?:FROM|JOIN)\s+(proj_[a-z][a-z0-9_]*)", re.IGNORECASE)


def _referenced_bc(table_name: str) -> str:
    override = _TABLE_OWNER_OVERRIDES.get(table_name)
    if override is not None:
        return override
    return table_name[len("proj_") :].split("_", 1)[0].lower()


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _bc_source_files() -> list[Path]:
    """Tracked `.py` files under `src/cora` (every BC's source).

    Widened from adapters-only: a cross-BC projection read can hide in a
    lifespan/bootstrap file at the BC root just as easily as in an
    adapter. Files without a `proj_*` read simply produce no matches.
    """
    return sorted(tracked_python_files())


@pytest.mark.architecture
@pytest.mark.parametrize("path", _bc_source_files(), ids=_qualified)
def test_bc_source_reads_only_its_own_bc_projection(path: Path) -> None:
    owning_bc = path.relative_to(CORA_ROOT).parts[0]
    text = path.read_text()

    offenders: list[str] = []
    for match in _PROJ_READ_RE.finditer(text):
        table_name = match.group(1).lower()
        referenced_bc = _referenced_bc(table_name)
        if referenced_bc == owning_bc:
            continue
        if (owning_bc, referenced_bc) in _CROSS_BC_READ_ALLOWLIST:
            continue
        lineno = text[: match.start()].count("\n") + 1
        offenders.append(
            f"line {lineno}: reads {table_name} owned by {referenced_bc!r} "
            f"(owning BC is {owning_bc!r})"
        )

    assert not offenders, (
        f"{_qualified(path)} reads another BC's projection table(s):\n  "
        + "\n  ".join(offenders)
        + "\n\nA BC's source may read only its OWN BC's proj_<bc>_* "
        "tables. Cross-BC integration goes through a port (the consumer "
        "shapes it, the owning BC ships the adapter), never a direct "
        "cross-projection SQL read. See chain-walk Anti-hook 2. If a "
        "cross-BC read is genuinely justified (requires a design memo), "
        "add the (owning_bc, referenced_bc) pair to "
        "_CROSS_BC_READ_ALLOWLIST in this file with a citation."
    )
