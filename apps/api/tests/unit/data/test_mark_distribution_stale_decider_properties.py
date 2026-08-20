"""Property-based tests for `mark_distribution_stale.decide` (Data BC).

Complements the example-based `test_mark_distribution_stale_decider.py`
with universal claims across generated inputs. The decider is a pure
guarded transition with actor attribution

    (state, command, now, marked_stale_by) -> list[DistributionMarkedStale]

Load-bearing properties:

  - state=None always raises `DistributionNotFoundError` carrying
    command.distribution_id.
  - Any non-Discarded status (Registered, Verified, Stale) always emits
    exactly one `DistributionMarkedStale` (distribution_id=state.id,
    occurred_at=now, marked_stale_by threaded); unlike discard_distribution
    there is no redundancy guard, so no sibling context is needed at all.
  - A Discarded status always raises `DistributionCannotMarkStaleError`.
  - The emitted event's distribution_id is `state.id`, never
    command.distribution_id.
  - Pure: same inputs return equal events.

The full guard-precedence (reason validation before the status guard) is
pinned by the example test; this file does not duplicate it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.aggregates.dataset.state import DatasetChecksum, DatasetEncoding
from cora.data.aggregates.distribution import (
    AccessProtocol,
    Distribution,
    DistributionCannotMarkStaleError,
    DistributionMarkedStale,
    DistributionNotFoundError,
    DistributionStatus,
    DistributionUri,
    TriggerSource,
)
from cora.data.features import mark_distribution_stale
from cora.data.features.mark_distribution_stale import MarkDistributionStale
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH
from tests._strategies import aware_datetimes, printable_ascii_text

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_DATASET_ID = UUID("01900000-0000-7000-8000-0000000000d1")
_reasons = printable_ascii_text(min_size=1, max_size=REASON_MAX_LENGTH)
_non_discarded_statuses = st.sampled_from(
    [DistributionStatus.REGISTERED, DistributionStatus.VERIFIED, DistributionStatus.STALE]
)


def _distribution(
    *, distribution_id: UUID, supply_id: UUID, status: DistributionStatus
) -> Distribution:
    return Distribution(
        id=distribution_id,
        dataset_id=_DATASET_ID,
        supply_id=supply_id,
        uri=DistributionUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        access_protocol=AccessProtocol.S3,
        registered_at=datetime(2026, 6, 28, tzinfo=UTC),
        registered_by=ActorId(_DATASET_ID),
        status=status,
    )


@pytest.mark.unit
@given(
    distribution_id=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    marked_stale_by_uuid=st.uuids(),
)
def test_mark_stale_with_none_state_always_raises_not_found(
    distribution_id: UUID,
    reason: str,
    now: datetime,
    marked_stale_by_uuid: UUID,
) -> None:
    """Empty stream always raises `DistributionNotFoundError` carrying
    command.distribution_id."""
    with pytest.raises(DistributionNotFoundError) as exc:
        mark_distribution_stale.decide(
            state=None,
            command=MarkDistributionStale(distribution_id=distribution_id, reason=reason),
            now=now,
            marked_stale_by=ActorId(marked_stale_by_uuid),
        )
    assert exc.value.distribution_id == distribution_id


@pytest.mark.unit
@given(
    distribution_id=st.uuids(),
    supply_id=st.uuids(),
    status=_non_discarded_statuses,
    reason=_reasons,
    now=aware_datetimes(),
    marked_stale_by_uuid=st.uuids(),
)
def test_mark_stale_any_non_discarded_status_emits_single_event(
    distribution_id: UUID,
    supply_id: UUID,
    status: DistributionStatus,
    reason: str,
    now: datetime,
    marked_stale_by_uuid: UUID,
) -> None:
    """Any non-Discarded status (Registered, Verified, Stale) always
    yields exactly one DistributionMarkedStale threaded with state.id +
    now + marked_stale_by. No sibling / redundancy context is consulted."""
    marked_stale_by = ActorId(marked_stale_by_uuid)
    target = _distribution(distribution_id=distribution_id, supply_id=supply_id, status=status)
    events = mark_distribution_stale.decide(
        state=target,
        command=MarkDistributionStale(distribution_id=distribution_id, reason=reason),
        now=now,
        marked_stale_by=marked_stale_by,
    )
    assert events == [
        DistributionMarkedStale(
            distribution_id=distribution_id,
            reason=reason,
            trigger=TriggerSource.OPERATOR.value,
            occurred_at=now,
            marked_stale_by=marked_stale_by,
        )
    ]


@pytest.mark.unit
@given(
    distribution_id=st.uuids(),
    supply_id=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    marked_stale_by_uuid=st.uuids(),
)
def test_mark_stale_discarded_status_always_raises_cannot_mark_stale(
    distribution_id: UUID,
    supply_id: UUID,
    reason: str,
    now: datetime,
    marked_stale_by_uuid: UUID,
) -> None:
    """Discarded is terminal: the guard always fires regardless of reason
    or actor, carrying the target's own id and current status."""
    target = _distribution(
        distribution_id=distribution_id,
        supply_id=supply_id,
        status=DistributionStatus.DISCARDED,
    )
    with pytest.raises(DistributionCannotMarkStaleError) as exc:
        mark_distribution_stale.decide(
            state=target,
            command=MarkDistributionStale(distribution_id=distribution_id, reason=reason),
            now=now,
            marked_stale_by=ActorId(marked_stale_by_uuid),
        )
    assert exc.value.distribution_id == distribution_id
    assert exc.value.current_status is DistributionStatus.DISCARDED


@pytest.mark.unit
@given(
    state_id=st.uuids(),
    command_id=st.uuids(),
    supply_id=st.uuids(),
    status=_non_discarded_statuses,
    reason=_reasons,
    now=aware_datetimes(),
    marked_stale_by_uuid=st.uuids(),
)
def test_mark_stale_uses_state_id_not_command_distribution_id(
    state_id: UUID,
    command_id: UUID,
    supply_id: UUID,
    status: DistributionStatus,
    reason: str,
    now: datetime,
    marked_stale_by_uuid: UUID,
) -> None:
    """The emitted event's distribution_id is state.id, not command.distribution_id."""
    target = _distribution(distribution_id=state_id, supply_id=supply_id, status=status)
    events = mark_distribution_stale.decide(
        state=target,
        command=MarkDistributionStale(distribution_id=command_id, reason=reason),
        now=now,
        marked_stale_by=ActorId(marked_stale_by_uuid),
    )
    assert events[0].distribution_id == state_id


@pytest.mark.unit
@given(
    distribution_id=st.uuids(),
    supply_id=st.uuids(),
    status=_non_discarded_statuses,
    reason=_reasons,
    now=aware_datetimes(),
    marked_stale_by_uuid=st.uuids(),
)
def test_mark_stale_is_pure_same_input_same_output(
    distribution_id: UUID,
    supply_id: UUID,
    status: DistributionStatus,
    reason: str,
    now: datetime,
    marked_stale_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    target = _distribution(distribution_id=distribution_id, supply_id=supply_id, status=status)
    command = MarkDistributionStale(distribution_id=distribution_id, reason=reason)
    marked_stale_by = ActorId(marked_stale_by_uuid)
    first = mark_distribution_stale.decide(
        state=target, command=command, now=now, marked_stale_by=marked_stale_by
    )
    second = mark_distribution_stale.decide(
        state=target, command=command, now=now, marked_stale_by=marked_stale_by
    )
    assert first == second
