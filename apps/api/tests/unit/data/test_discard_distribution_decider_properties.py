"""Property-based tests for `discard_distribution.decide` (Data BC).

Complements the example-based `test_discard_distribution_decider.py`
with universal claims across generated inputs. The decider is a pure
guarded transition with actor attribution

    (state, command, context, now, discarded_by) -> list[DistributionDiscarded]

Load-bearing properties:

  - state=None always raises `DistributionNotFoundError` carrying
    command.distribution_id.
  - With a non-Discarded copy, a non-Discarded parent Dataset, and at
    least one sibling Verified on a different supply_id, exactly one
    `DistributionDiscarded` is emitted (distribution_id=state.id,
    occurred_at=now, discarded_by threaded).
  - A sibling Verified on the SAME supply_id as the target never
    satisfies the redundancy invariant: with no other-tier Verified
    sibling, `DistributionCannotDiscardLastVerifiedError` always raises.
  - The emitted event's distribution_id is `state.id`, never
    command.distribution_id.
  - Pure: same inputs return equal events.

The full guard-precedence matrix (re-discard, parent-Discarded, reason
validation order) is pinned by the example test; this file does not
duplicate it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Dataset,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetStatus,
    DatasetUri,
)
from cora.data.aggregates.distribution import (
    AccessProtocol,
    Distribution,
    DistributionCannotDiscardLastVerifiedError,
    DistributionDiscarded,
    DistributionNotFoundError,
    DistributionStatus,
    DistributionUri,
)
from cora.data.features import discard_distribution
from cora.data.features.discard_distribution import DiscardDistribution
from cora.data.features.discard_distribution.context import DiscardDistributionContext
from cora.infrastructure.ports.dataset_distribution_lookup import (
    DatasetDistributionLookupResult,
)
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH
from tests._strategies import aware_datetimes, printable_ascii_text

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_DATASET_ID = UUID("01900000-0000-7000-8000-0000000000d1")
_reasons = printable_ascii_text(min_size=1, max_size=REASON_MAX_LENGTH)


def _dataset(*, status: DatasetStatus = DatasetStatus.REGISTERED) -> Dataset:
    return Dataset(
        id=_DATASET_ID,
        name=DatasetName("seed"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        status=status,
    )


def _distribution(*, distribution_id: UUID, supply_id: UUID) -> Distribution:
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
        status=DistributionStatus.REGISTERED,
    )


def _sibling(*, supply_id: UUID, status: str) -> DatasetDistributionLookupResult:
    return DatasetDistributionLookupResult(
        distribution_id=uuid4(),
        dataset_id=_DATASET_ID,
        supply_id=supply_id,
        status=status,
    )


@pytest.mark.unit
@given(
    distribution_id=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_with_none_state_always_raises_not_found(
    distribution_id: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """Empty stream always raises `DistributionNotFoundError` carrying
    command.distribution_id."""
    context = DiscardDistributionContext(dataset=_dataset(), sibling_distributions=())
    with pytest.raises(DistributionNotFoundError) as exc:
        discard_distribution.decide(
            state=None,
            command=DiscardDistribution(distribution_id=distribution_id, reason=reason),
            context=context,
            now=now,
            discarded_by=ActorId(discarded_by_uuid),
        )
    assert exc.value.distribution_id == distribution_id


@pytest.mark.unit
@given(
    distribution_id=st.uuids(),
    target_supply=st.uuids(),
    sibling_supply=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_emits_single_event_with_other_tier_verified_sibling(
    distribution_id: UUID,
    target_supply: UUID,
    sibling_supply: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """A Verified sibling on a different tier always yields exactly one
    DistributionDiscarded threaded with state.id + now + discarded_by."""
    assume(target_supply != sibling_supply)
    discarded_by = ActorId(discarded_by_uuid)
    target = _distribution(distribution_id=distribution_id, supply_id=target_supply)
    sibling = _sibling(supply_id=sibling_supply, status="Verified")
    context = DiscardDistributionContext(dataset=_dataset(), sibling_distributions=(sibling,))
    events = discard_distribution.decide(
        state=target,
        command=DiscardDistribution(distribution_id=distribution_id, reason=reason),
        context=context,
        now=now,
        discarded_by=discarded_by,
    )
    assert events == [
        DistributionDiscarded(
            distribution_id=distribution_id,
            reason=reason,
            occurred_at=now,
            discarded_by=discarded_by,
        )
    ]


@pytest.mark.unit
@given(
    distribution_id=st.uuids(),
    target_supply=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_same_tier_verified_sibling_never_satisfies_redundancy(
    distribution_id: UUID,
    target_supply: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """A Verified sibling on the SAME supply_id as the target is not
    redundancy on a different tier; the last-verified guard always raises."""
    target = _distribution(distribution_id=distribution_id, supply_id=target_supply)
    same_tier = _sibling(supply_id=target_supply, status="Verified")
    context = DiscardDistributionContext(dataset=_dataset(), sibling_distributions=(same_tier,))
    with pytest.raises(DistributionCannotDiscardLastVerifiedError) as exc:
        discard_distribution.decide(
            state=target,
            command=DiscardDistribution(distribution_id=distribution_id, reason=reason),
            context=context,
            now=now,
            discarded_by=ActorId(discarded_by_uuid),
        )
    assert exc.value.distribution_id == distribution_id


@pytest.mark.unit
@given(
    state_id=st.uuids(),
    command_id=st.uuids(),
    target_supply=st.uuids(),
    sibling_supply=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_uses_state_id_not_command_distribution_id(
    state_id: UUID,
    command_id: UUID,
    target_supply: UUID,
    sibling_supply: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """The emitted event's distribution_id is state.id, not command.distribution_id."""
    assume(state_id != command_id)
    assume(target_supply != sibling_supply)
    target = _distribution(distribution_id=state_id, supply_id=target_supply)
    sibling = _sibling(supply_id=sibling_supply, status="Verified")
    context = DiscardDistributionContext(dataset=_dataset(), sibling_distributions=(sibling,))
    events = discard_distribution.decide(
        state=target,
        command=DiscardDistribution(distribution_id=command_id, reason=reason),
        context=context,
        now=now,
        discarded_by=ActorId(discarded_by_uuid),
    )
    assert events[0].distribution_id == state_id


@pytest.mark.unit
@given(
    distribution_id=st.uuids(),
    target_supply=st.uuids(),
    sibling_supply=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_is_pure_same_input_same_output(
    distribution_id: UUID,
    target_supply: UUID,
    sibling_supply: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    assume(target_supply != sibling_supply)
    target = _distribution(distribution_id=distribution_id, supply_id=target_supply)
    sibling = _sibling(supply_id=sibling_supply, status="Verified")
    context = DiscardDistributionContext(dataset=_dataset(), sibling_distributions=(sibling,))
    command = DiscardDistribution(distribution_id=distribution_id, reason=reason)
    discarded_by = ActorId(discarded_by_uuid)
    first = discard_distribution.decide(
        state=target, command=command, context=context, now=now, discarded_by=discarded_by
    )
    second = discard_distribution.decide(
        state=target, command=command, context=context, now=now, discarded_by=discarded_by
    )
    assert first == second
