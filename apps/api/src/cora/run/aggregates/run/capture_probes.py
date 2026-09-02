"""Capture probe entry: append-only record of reach to the capture-watch substrate.

The write half of the coverage-window seam for the Run BC's
capture-observe path (memory/project_witnessed_run_prelive_slices.md,
slice 16), mirroring `entries_enclosure_permit_probes`
(`enclosure/aggregates/enclosure/permit_probes.py`,
[[project_enclosure_permit_probe_design]]): one table answers what the
substrate said (the `CaptureLifecycleObservation.phase` a
`ControlPortCaptureObserver` pump surfaces), this one answers whether
CORA could reach it. `reach_tier` is already computed on every capture
observation and was previously thrown away, reaching only a log line
(`run_translator.capture_unreached` in `_run_translator.py`).

## Scoped by `capture_code`, not a minted aggregate id

Unlike `PermitProbe` (scoped by `enclosure_id`, a real persistent
aggregate) or `FeedHeartbeat` (scoped by `run_id`, a promoted Run), a
capture code has no backing aggregate anywhere in this codebase: it is
a bare deployment-declared string (`Settings.capture_watch_pvs`'s outer
key), already CORA's declared identifier for a watched source
elsewhere (`external_refs`'s `Identifier(scheme="capture-code", ...)`,
`_capture_baseline_reader.py`, `_capture_experiment_identity_reader.py`,
every `run_translator.capture_*` log line). Minting a `CaptureSource`
aggregate purely to get a UUID scope key would model the exact
TomoScan-orchestration concept CORA's own seam intends to dissolve
(memory/project_seam_model.md), on a rule-of-three count of one. Reach
is a property of the CHANNEL, which outlives every Run -- the same
reason `run_id` cannot work here either: the whole point of this trail
is to cover the gaps BETWEEN Runs, when no run_id exists at all.

This is the first entries table scoped by a string rather than an
aggregate id, and `record_export._registry`'s `EntriesReader` type is
widened (`UUID | str`) to accommodate it; see that module's docstring
for the export-reachability argument.

## One row per (capture_code, PV), never collapsed per code

A capture code can pump several independently-subscribed PVs (`status`
required, `abort` optional per `Settings.capture_watch_pvs`); each
carries its own `source_id`. This table takes one row per observation
per PV, mirroring `PermitProbe`'s one-row-per-observation shape
exactly -- it is never rolled up to one row per code, since two PVs on
the same code can lose and regain reach independently.

## `phase_claimed`, mirroring `PermitProbe.status_claimed`

Records whether the observation this probe accompanies also carried a
`CaptureLifecycleObservation.phase` claim (a real status push, or an
asserted `abort` reading) as opposed to being probe-only (a periodic
re-affirmation poll tick) or a disconnect/clean-stream-end
(`_unreached` in `_capture_observer.py`), both of which carry
`phase=None`. A fact about the PROBE, not the capture: this row never
carries the observed phase itself.

## `observed_at` diverges deliberately from the `PermitProbe` precedent

`PermitProbe` carries only `recorded_at`. That is NOT because no
producer timestamp crosses the `EnclosureObserver` port --
`EnclosureObservation.observed_at` exists and reaches the enclosure's
own transition event (`enclosure_observer.py`'s own docstring says so
in as many words) -- it is a scoping choice the permit-probe design
made for its own row shape. This design makes the different, deliberate
choice to carry `CaptureLifecycleObservation.observed_at` (nullable --
`None` for `_unreached` / probe-only ticks, the substrate's own read
time for a real push) on every row: the observation already carries the
field, carrying it costs nothing, and it is real freshness evidence a
reader would otherwise have to reconstruct from `recorded_at` alone.

## Expected volume

Verified from source, not assumed: the ~10s cadence measured in the
2026-08-14 2-BM outage's `capture_unreached` log lines is
`_run_translator.py`'s own `_RECONNECT_DELAY_SECONDS` (5.0s) plus
`EpicsCaControlPort._DEFAULT_TIMEOUT_S` (5.0s) -- the identical
mechanism the enclosure gate review diagnosed for permit probes, NOT
`Settings.capture_watch_probe_tick_seconds` (irrelevant while
disconnected: `_poll` is recreated fresh inside every `_drain` call and
is cancelled within ~5s of a dead reconnect, long before its first
tick), and NOT `Settings.capture_progress_flush_tick_seconds` (a
numerically coincidental 10.0s default governing an unrelated
mechanism, the progress feeder's flush cadence). Expect roughly
8,640 x (number of PVs reaching `observe_capture` for a code) rows/day
while that code's substrate is fully unreachable; fewer while
push-driven and healthy, or governed by `capture_watch_probe_tick_seconds`
while connected-but-quiet. This scales with configured roles (2-BM
declares `status` + `abort` today: two independent reach streams per
code), not a single constant.

At `capture_watch_probe_tick_seconds`'s default (`None`, matching
`enclosure_permit_probe_tick_seconds`'s own default), coverage is
PUSH-ONLY: a connected-but-quiet code produces zero rows, exactly like
a genuinely dead process would. Configuring the tick is what makes a
long idle window distinguishable from a wedged one; an unconfigured
deployment gets disconnect coverage only, inherited from the identical
default on the shipped permit-probe precedent, not a new gap this
table introduces.

Mirrors `PermitProbe`'s per-category-writer pattern: a typed dataclass
+ a category-local Protocol + Postgres / InMemory adapters, BC-internal
(NOT a shared cross-BC port). Append-only INSERT: the entries_* table
is REVOKEd from UPDATE, and there is no natural key to deduplicate
against (`event_id` is a fresh id per observation), so this store does
not need `ON CONFLICT`, matching `PermitProbeStore`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg

from cora.shared.reach import ReachTier


@dataclass(frozen=True)
class CaptureProbe:
    """One reach observation for a capture-watch code's substrate PV.

    `event_id` is the producer-assigned UUIDv7 dedup key (PK).
    `capture_code` is the deployment-declared watch code
    (`Settings.capture_watch_pvs`'s outer key); `source_kind` /
    `source_id` name the specific PV this row's reach evidence came
    from (mirrors `MonitorRef`'s attribution pair). `phase_claimed`
    records whether the accompanying observation also carried a
    `CaptureLifecycleObservation.phase` claim; see this module's
    docstring. `observed_at` is the substrate's own read time
    (`CaptureLifecycleObservation.observed_at`), `None` for a
    probe-only tick or an unreached/disconnected read. `recorded_at`
    (DB DEFAULT now()) is the trust anchor and is not carried on this
    row.
    """

    event_id: UUID
    capture_code: str
    source_kind: str
    source_id: str
    reach_tier: ReachTier
    phase_claimed: bool
    observed_at: datetime | None


class CaptureProbeStore(Protocol):
    """Per-category port for capture-probe writes (BC-internal)."""

    async def append(self, rows: list[CaptureProbe]) -> None: ...


_APPEND_SQL = """
INSERT INTO entries_run_capture_probes (
    event_id, capture_code, source_kind, source_id, reach_tier,
    phase_claimed, observed_at
) VALUES ($1, $2, $3, $4, $5, $6, $7)
"""


class PostgresCaptureProbeStore:
    """asyncpg-backed `CaptureProbeStore`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, rows: list[CaptureProbe]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_SQL,
                [
                    (
                        r.event_id,
                        r.capture_code,
                        r.source_kind,
                        r.source_id,
                        r.reach_tier.value,
                        r.phase_claimed,
                        r.observed_at,
                    )
                    for r in rows
                ],
            )


class InMemoryCaptureProbeStore:
    """Test / `app_env=test` adapter; list of every row appended."""

    def __init__(self) -> None:
        self._rows: list[CaptureProbe] = []

    async def append(self, rows: list[CaptureProbe]) -> None:
        self._rows.extend(rows)

    def all(self) -> list[CaptureProbe]:
        return list(self._rows)


__all__ = [
    "CaptureProbe",
    "CaptureProbeStore",
    "InMemoryCaptureProbeStore",
    "PostgresCaptureProbeStore",
]
