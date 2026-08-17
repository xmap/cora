"""Unit tests for the capture-probe store (slice 16's coverage trail).

Mirrors `test_feed_heartbeats.py`'s shape. Unlike `FeedHeartbeatStore`,
this store does NOT dedup on `event_id` client-side: there is no
natural dedup key (a fresh id is minted per observation) and no
`ON CONFLICT`, matching `InMemoryPermitProbeStore`'s own plain-list
shape rather than `InMemoryFeedHeartbeatStore`'s dict. NOTE: unlike
`InMemoryFeedHeartbeatStore` (whose dict shape mirrors its table's real
`ON CONFLICT DO NOTHING`), `InMemoryCaptureProbeStore`'s plain list does
NOT mirror `entries_run_capture_probes`' real `event_id uuid PRIMARY KEY`
constraint -- two rows sharing an `event_id` would raise
`UniqueViolationError` against Postgres. That case never arises in
practice (`event_id` is always freshly minted per observation) and is
deliberately not exercised below.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.run.aggregates.run import CaptureProbe, InMemoryCaptureProbeStore
from cora.shared.reach import ReachTier

_T0 = datetime(2026, 8, 14, 17, 19, 31, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return _T0 + timedelta(seconds=seconds)


def _probe(
    *,
    capture_code: str = "2bmb-tomoscan",
    source_id: str = "2bmb:TomoScan:ScanStatus",
    reach_tier: ReachTier = ReachTier.UNREACHED,
    phase_claimed: bool = False,
    observed_at: datetime | None = None,
) -> CaptureProbe:
    return CaptureProbe(
        event_id=uuid4(),
        capture_code=capture_code,
        source_kind="EpicsPv",
        source_id=source_id,
        reach_tier=reach_tier,
        phase_claimed=phase_claimed,
        observed_at=observed_at,
    )


@pytest.mark.unit
async def test_store_append_retains_rows_across_separate_calls_in_order() -> None:
    """Unlike `FeedHeartbeatStore`'s dict, this store performs no
    client-side dedup at all: successive `.append()` calls accumulate,
    in order. Two DISTINCT rows here, each with its own event_id --
    see the module docstring for why a shared event_id is not a case
    this store is exercised against."""
    store = InMemoryCaptureProbeStore()
    first = _probe()
    second = _probe(reach_tier=ReachTier.RELAYED, phase_claimed=True, observed_at=_at(10))
    await store.append([first])
    await store.append([second])
    assert store.all() == [first, second]


@pytest.mark.unit
async def test_store_append_is_a_noop_for_an_empty_list() -> None:
    store = InMemoryCaptureProbeStore()
    await store.append([])
    assert store.all() == []


@pytest.mark.unit
async def test_probe_carries_both_observed_at_and_allows_none() -> None:
    """`observed_at` is nullable (unreached / probe-only) and, when set,
    is carried through unchanged -- the deliberate divergence from
    `PermitProbe`, which has no producer timestamp at all."""
    store = InMemoryCaptureProbeStore()
    unreached = _probe(reach_tier=ReachTier.UNREACHED, phase_claimed=False, observed_at=None)
    pushed = _probe(
        source_id="2bmb:TomoScan:AbortScan",
        reach_tier=ReachTier.RELAYED,
        phase_claimed=True,
        observed_at=_at(5),
    )
    await store.append([unreached, pushed])
    rows = store.all()
    assert rows[0].observed_at is None
    assert rows[1].observed_at == _at(5)
    assert rows[0].source_id != rows[1].source_id


@pytest.mark.unit
async def test_probe_is_scoped_by_capture_code_not_a_uuid() -> None:
    """Two different capture codes on the same substrate PV family are
    distinct rows; nothing collapses them (see the module docstring's
    "one row per (capture_code, PV)" argument)."""
    store = InMemoryCaptureProbeStore()
    await store.append(
        [_probe(capture_code="2bmb-tomoscan"), _probe(capture_code="2bmb-tomoscan-fpga")]
    )
    codes = {row.capture_code for row in store.all()}
    assert codes == {"2bmb-tomoscan", "2bmb-tomoscan-fpga"}
