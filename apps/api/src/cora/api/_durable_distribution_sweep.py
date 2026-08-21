"""Finding Runs whose durable copy CORA has not recorded yet.

The acquisition tier is transient. A finished scan lands on fast local
disk, an operator later copies the experiment to APS Data Management
under `/gdata`, and the upstream tiers are capacity-purged with no
fixed schedule (`/data2` was lost outright on 2026-08-14). A record
naming only the acquisition path therefore points at bytes that will be
gone, so CORA has to record the durable copy as a SECOND Distribution
on the SAME Dataset.

Second Distribution, not second Dataset: the Data BC is DCAT-3, where a
Dataset is the content identity and a Distribution is one byte-copy of
it at one Supply (see `data.aggregates.distribution.state`). The durable
copy is byte-identical, so a second Dataset would claim two scientific
contents for one set of bytes. `register_distribution` already exists
and needs no change.

## Why this query is the INVERSE of the ingestor's

`_capture_scan_ingestor._CANDIDATE_SQL` wants Runs with NO Dataset: it
performs genesis, once per Run. This one wants Runs that DO have a
Dataset and do NOT yet have a Distribution at a durable Supply. Do not
try to serve both from one query; they disagree on every clause that
matters.

## What a candidate must carry, and why each part is available

Finding the durable copy means naming a path CORA cannot construct. At
2-BM the experiment folder is `{yyyy-mm}-{PIsurname}-{GUP}` and CORA
deliberately holds no surname, so the search runs on the parts it does
hold: the proposal number as a directory suffix, and the filename. See
`cora.data._remote_scan_probe`'s `locate` op for the other side.

A Run with NO recorded proposal number is therefore not a candidate,
and this query says so with an explicit `IS NOT NULL` rather than
letting the join drop it silently. That is a decision, not an
oversight: measured on the real tree, scan filenames are NOT unique
across a month (the worst month holds 45 duplicates), so there is no
safe way to search on filename alone. Without a proposal number there
is no search key at all, and inventing one would mean registering
someone else's bytes against this Dataset.

## Personal data

`observed_path` is the one field here that carries a surname, and it is
carried for exactly two derived values: the filename to search for, and
the experiment month to search under. It must never reach a log line.
The `run_capture_path` vault is erasable precisely so this value can be
deleted; a log sink is not.
"""

# asyncpg's own stubs type every row value as `Any`, so reading a
# column is unavoidably unknown-typed here. Suppressed at module level,
# matching `_capture_scan_ingestor`'s identical situation.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    import asyncpg

_MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})")

_CANDIDATE_SQL = """
SELECT dds.dataset_id,
       rcp.run_id,
       rcp.observed_path,
       rcp.root,
       prs.capture_code,
       rei.proposal_number
FROM proj_data_dataset_summary dds
JOIN run_capture_path rcp ON rcp.run_id = dds.producing_run_id
JOIN proj_run_summary prs ON prs.run_id = dds.producing_run_id
JOIN run_experiment_identity rei ON rei.run_id = dds.producing_run_id
WHERE dds.producing_run_id IS NOT NULL
  AND dds.status = 'Registered'
  AND prs.capture_code IS NOT NULL
  -- No proposal number, no search key. See the module docstring: the
  -- filename alone is not unique enough to search on, so this is a
  -- refusal to guess rather than a join that quietly drops the row.
  AND rei.proposal_number IS NOT NULL
  -- The acquisition-tier row, which is what carries the filename and
  -- the experiment month. A row already AT a durable root is the
  -- answer, not the question.
  AND rcp.host IS NOT NULL
  AND rcp.root IS NOT NULL
  AND NOT (rcp.root = ANY($2::text[]))
  AND NOT (dds.dataset_id = ANY($1::uuid[]))
  AND NOT EXISTS (
      SELECT 1 FROM proj_data_distribution_summary pdd
      WHERE pdd.dataset_id = dds.dataset_id
        AND pdd.supply_id = ANY($3::uuid[])
        -- A discarded Distribution is not a recorded durable copy, so
        -- the Dataset becomes a candidate again. Mirrors the partial
        -- unique index on (dataset_id, supply_id, uri), which also
        -- excludes discarded rows so a re-register is permitted.
        AND pdd.status <> 'Discarded'
  )
ORDER BY dds.created_at ASC
LIMIT 1
"""


def months_to_search(observed_path: str, root: str) -> tuple[str, ...]:
    """The month directories the durable copy may be filed under.

    The experiment folder is the first path segment below `root`, and
    under the current naming scheme it opens with the month the
    BEAMTIME was scheduled in. That is not always the month the scan
    ran: beamtime straddles month boundaries, so a scan taken on the
    1st can belong to an experiment filed under the previous month.
    Searching only one month would miss such a run silently, and since
    no match means keep waiting rather than give up, it would miss it
    forever.

    Returns the folder's own month plus its two neighbours, newest
    first, or an empty tuple when the first segment does not open with
    a `YYYY-MM`. Empty means "do not search", never "search
    everything": the archive goes back to 2020 and folders older than
    2025-07 use a different scheme with no proposal number in the name
    at all, so a widened search could only ever return a wrong answer
    more expensively.
    """
    relative = (
        PurePosixPath(observed_path).relative_to(root) if _is_under(observed_path, root) else None
    )
    if relative is None or not relative.parts:
        return ()
    match = _MONTH_PATTERN.match(relative.parts[0])
    if match is None:
        return ()
    year, month = int(match.group(1)), int(match.group(2))
    return tuple(_shift_month(year, month, offset) for offset in (0, -1, 1))


def _is_under(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def _shift_month(year: int, month: int, offset: int) -> str:
    index = (year * 12 + (month - 1)) + offset
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


@dataclass(frozen=True)
class DurableDistributionCandidate:
    """One Dataset whose durable copy has not been recorded yet."""

    dataset_id: UUID
    run_id: UUID
    capture_code: str
    proposal_number: str
    observed_path: str
    """The ACQUISITION-tier path. Personal data: it embeds the PI
    surname through the experiment folder name. Carried only to derive
    the filename and the months to search, and never logged."""
    acquisition_root: str

    @property
    def filename(self) -> str:
        """The scan file's own name, which carries no personal data and
        is safe to log. The surname lives in the directory part."""
        return PurePosixPath(self.observed_path).name

    @property
    def directory_suffix(self) -> str:
        """What the experiment folder must end with. The leading hyphen
        is load bearing: without it a proposal of `1015116` would also
        match a folder ending `11015116`."""
        return f"-{self.proposal_number}"


class DurableDistributionCandidateLookup(Protocol):
    """Composition-root-owned read: joins the Run BC's own
    `run_capture_path` / `run_experiment_identity` / `proj_run_summary`
    against the Data BC's Dataset and Distribution projections. Neither
    BC owns this query alone, mirroring `main.py`'s "only cora.api may
    depend on both" placement rule.

    `exclude` holds `dataset_id` values. The unit of work is one
    Dataset's durable copy, so a tick that gives up on a Dataset must
    not re-select it, while a Run's OTHER Datasets stay reachable.
    """

    async def next_candidate(
        self, *, exclude: frozenset[UUID] = frozenset()
    ) -> DurableDistributionCandidate | None: ...


class PostgresDurableDistributionCandidateLookup:
    """Production `DurableDistributionCandidateLookup`."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        durable_roots: tuple[str, ...],
        durable_supply_ids: tuple[UUID, ...],
    ) -> None:
        self._pool = pool
        self._durable_roots = durable_roots
        self._durable_supply_ids = durable_supply_ids

    async def next_candidate(
        self, *, exclude: frozenset[UUID] = frozenset()
    ) -> DurableDistributionCandidate | None:
        if not self._durable_roots or not self._durable_supply_ids:
            return None
        row = await self._pool.fetchrow(  # pyright: ignore[reportUnknownMemberType]
            _CANDIDATE_SQL,
            list(exclude),
            list(self._durable_roots),
            list(self._durable_supply_ids),
        )
        if row is None:
            return None
        return DurableDistributionCandidate(
            dataset_id=row["dataset_id"],
            run_id=row["run_id"],
            capture_code=row["capture_code"],
            proposal_number=row["proposal_number"],
            observed_path=row["observed_path"],
            acquisition_root=row["root"],
        )


class NeverDurableDistributionCandidateLookup:
    """No-pool fallback (in-memory deployment / test env): no projection
    to probe, so there is never a candidate, mirroring
    `NeverScanIngestCandidateLookup`'s own shape."""

    async def next_candidate(
        self, *, exclude: frozenset[UUID] = frozenset()
    ) -> DurableDistributionCandidate | None:
        _ = exclude
        return None


__all__ = [
    "DurableDistributionCandidate",
    "DurableDistributionCandidateLookup",
    "NeverDurableDistributionCandidateLookup",
    "PostgresDurableDistributionCandidateLookup",
    "months_to_search",
]
