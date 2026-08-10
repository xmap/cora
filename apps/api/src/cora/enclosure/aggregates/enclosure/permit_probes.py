"""Permit probe entry: append-only record of reach to the permit substrate.

The write half of the coverage-window seam
([[project_enclosure_permit_probe_design]]). The Enclosure BC's permit
monitor writes one `PermitProbe` per observation its `EnclosureObserver`
surfaces, so the read side can tell "the hutch has genuinely been
secure for six hours" from "CORA was not looking for six hours and got
lucky". `permit_status` (on `proj_enclosure_summary`) answers what the
interlock said; this table answers whether CORA could reach it. Neither
substitutes for the other, and this module carries no permit value.

Mirrors the `FeedHeartbeat` per-category-writer pattern: a typed
dataclass + a category-local Protocol + Postgres / InMemory adapters,
BC-internal (NOT a shared cross-BC port). Append-only INSERT: the
entries_* table is REVOKEd from UPDATE, and there is no natural key to
deduplicate against (`event_id` is a fresh id per observation), so
unlike `FeedHeartbeatStore` this store does not need `ON CONFLICT`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

import asyncpg


class ReachTier(StrEnum):
    """How CORA reached the permit substrate for one observation.

    Two values ship in v1. `RELAYED` means CORA received or fetched a
    value through the configured channel; `UNREACHED` means it could
    not, this tick. A stronger tier for a confirmed direct round trip to
    the authoritative source (as opposed to an intermediary, such as an
    EPICS CA gateway that may answer from its own cache) is deliberately
    NOT defined here: no producer in this codebase can currently prove
    one, and an unearned strong claim is worse than none. Adding a value
    later needs no migration, since the column is a length-CHECK, not a
    value-enumerating CHECK.
    """

    RELAYED = "Relayed"
    UNREACHED = "Unreached"


@dataclass(frozen=True)
class PermitProbe:
    """One reach observation for an Enclosure's permit substrate.

    `event_id` is the producer-assigned UUIDv7 dedup key (PK). `source_kind`
    / `source_id` mirror the attribution pair on `MonitorRef` (the same
    substrate, e.g. an EPICS PV). `status_claimed` records whether the
    observation this probe accompanies also carried a permit-status claim
    (a push delivery, or a real substrate disconnect) as opposed to being
    probe-only (a periodic re-affirmation read that makes no status
    claim). This is a fact about the PROBE, not the hutch: the probe row
    never carries the observed permit value itself. `recorded_at` (DB
    DEFAULT now()) is the trust anchor and is not carried on this row, no
    producer-asserted timestamp exists to pair it with.
    """

    event_id: UUID
    enclosure_id: UUID
    source_kind: str
    source_id: str
    reach_tier: ReachTier
    status_claimed: bool


class PermitProbeStore(Protocol):
    """Per-category port for permit-probe writes (BC-internal)."""

    async def append(self, rows: list[PermitProbe]) -> None: ...


_APPEND_SQL = """
INSERT INTO entries_enclosure_permit_probes (
    event_id, enclosure_id, source_kind, source_id, reach_tier, status_claimed
) VALUES ($1, $2, $3, $4, $5, $6)
"""


class PostgresPermitProbeStore:
    """asyncpg-backed `PermitProbeStore`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, rows: list[PermitProbe]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_SQL,
                [
                    (
                        r.event_id,
                        r.enclosure_id,
                        r.source_kind,
                        r.source_id,
                        r.reach_tier.value,
                        r.status_claimed,
                    )
                    for r in rows
                ],
            )


class InMemoryPermitProbeStore:
    """Test / `app_env=test` adapter; list of every row appended."""

    def __init__(self) -> None:
        self._rows: list[PermitProbe] = []

    async def append(self, rows: list[PermitProbe]) -> None:
        self._rows.extend(rows)

    def all(self) -> list[PermitProbe]:
        return list(self._rows)


__all__ = [
    "InMemoryPermitProbeStore",
    "PermitProbe",
    "PermitProbeStore",
    "PostgresPermitProbeStore",
    "ReachTier",
]
