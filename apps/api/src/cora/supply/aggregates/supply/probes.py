"""Supply probe entry: append-only record of reach to a Supply's substrate.

The write half of the coverage-window seam, mirrored from the Enclosure
BC's `permit_probes.py`. The Supply BC's status monitor writes one
`SupplyProbe` per observation its `SupplyObserver` surfaces, so the read
side can tell "the cooling water has genuinely read clear for six
hours" from "CORA was not looking for six hours and got lucky".
`proj_supply_summary.status` answers what BLEPS reported; this table
answers whether CORA could reach it. Neither substitutes for the other,
and this module carries no status value.

Mirrors the `PermitProbe` / `FeedHeartbeat` per-category-writer pattern:
a typed dataclass + a category-local Protocol + Postgres / InMemory
adapters, BC-internal (NOT a shared cross-BC port). Append-only INSERT:
the entries_* table is REVOKEd from UPDATE, and there is no natural key
to deduplicate against (`event_id` is a fresh id per observation).

`ReachTier` is `cora.shared.reach`'s hoisted vocabulary (Enclosure
originated it, Run/capture and now Supply reuse it); re-exported here so
every import of `ReachTier` from this module works the same as its
sibling.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import asyncpg

from cora.shared.reach import ReachTier


@dataclass(frozen=True)
class SupplyProbe:
    """One reach observation for a Supply's observation substrate.

    `event_id` is the producer-assigned UUIDv7 dedup key (PK).
    `source_kind` / `source_id` mirror the attribution pair on
    `MonitorRef` (the BLEPS channel PV that produced this reading).
    `status_claimed` records whether the observation this probe
    accompanies also carried a status claim (the aggregated BLEPS
    verdict resolved to tripped or clear) as opposed to being probe-only
    (a periodic re-affirmation read that makes no status claim). This is
    a fact about the PROBE, not the resource: the probe row never
    carries the observed status itself. `recorded_at` (DB DEFAULT now())
    is the trust anchor and is not carried on this row; no
    producer-asserted timestamp exists to pair it with.
    """

    event_id: UUID
    supply_id: UUID
    source_kind: str
    source_id: str
    reach_tier: ReachTier
    status_claimed: bool


class SupplyProbeStore(Protocol):
    """Per-category port for Supply-probe writes (BC-internal)."""

    async def append(self, rows: list[SupplyProbe]) -> None: ...


_APPEND_SQL = """
INSERT INTO entries_supply_probes (
    event_id, supply_id, source_kind, source_id, reach_tier, status_claimed
) VALUES ($1, $2, $3, $4, $5, $6)
"""


class PostgresSupplyProbeStore:
    """asyncpg-backed `SupplyProbeStore`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, rows: list[SupplyProbe]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_SQL,
                [
                    (
                        r.event_id,
                        r.supply_id,
                        r.source_kind,
                        r.source_id,
                        r.reach_tier.value,
                        r.status_claimed,
                    )
                    for r in rows
                ],
            )


class InMemorySupplyProbeStore:
    """Test / `app_env=test` adapter; list of every row appended."""

    def __init__(self) -> None:
        self._rows: list[SupplyProbe] = []

    async def append(self, rows: list[SupplyProbe]) -> None:
        self._rows.extend(rows)

    def all(self) -> list[SupplyProbe]:
        return list(self._rows)


__all__ = [
    "InMemorySupplyProbeStore",
    "PostgresSupplyProbeStore",
    "ReachTier",
    "SupplyProbe",
    "SupplyProbeStore",
]
