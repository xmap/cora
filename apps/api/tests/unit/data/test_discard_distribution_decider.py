"""Unit tests for the `discard_distribution` slice's pure decider.

Guarded primitive: a Distribution copy may be marked Discarded only
when a SIBLING copy of the same Dataset is Verified on a DIFFERENT
storage tier, AND the parent Dataset is not itself Discarded. Strict
semantics (re-discarding raises). Reason validated via
DistributionDiscardReason VO before the state guards.

The sibling-Verified signal is read from the projection-backed
DatasetDistributionLookupResult set carried on the context, NOT from
folding sibling Distribution aggregates.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

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
    DistributionCannotDiscardError,
    DistributionCannotDiscardLastVerifiedError,
    DistributionCannotDiscardUnderDiscardedDatasetError,
    DistributionDiscarded,
    DistributionNotFoundError,
    DistributionStatus,
    DistributionUri,
    InvalidDistributionDiscardReasonError,
)
from cora.data.features import discard_distribution
from cora.data.features.discard_distribution import DiscardDistribution
from cora.data.features.discard_distribution.context import DiscardDistributionContext
from cora.infrastructure.ports.dataset_distribution_lookup import (
    DatasetDistributionLookupResult,
)
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)
_DISCARDED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000099"))
_DATASET_ID = UUID("01900000-0000-7000-8000-0000000000d1")
_SUPPLY_A = UUID("01900000-0000-7000-8000-0000000000a1")
_SUPPLY_B = UUID("01900000-0000-7000-8000-0000000000b1")


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


def _distribution(
    *,
    distribution_id: UUID,
    supply_id: UUID,
    status: DistributionStatus = DistributionStatus.REGISTERED,
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
        registered_at=_NOW,
        registered_by=_DISCARDED_BY,
        status=status,
    )


def _sibling(
    *,
    distribution_id: UUID,
    supply_id: UUID,
    status: str,
) -> DatasetDistributionLookupResult:
    return DatasetDistributionLookupResult(
        distribution_id=distribution_id,
        dataset_id=_DATASET_ID,
        supply_id=supply_id,
        status=status,
    )


def _context(
    *,
    siblings: tuple[DatasetDistributionLookupResult, ...],
    dataset_status: DatasetStatus = DatasetStatus.REGISTERED,
) -> DiscardDistributionContext:
    return DiscardDistributionContext(
        dataset=_dataset(status=dataset_status),
        sibling_distributions=siblings,
    )


@pytest.mark.unit
def test_decide_emits_discarded_when_verified_sibling_on_different_tier() -> None:
    target = _distribution(distribution_id=uuid4(), supply_id=_SUPPLY_A)
    sibling = _sibling(distribution_id=uuid4(), supply_id=_SUPPLY_B, status="Verified")
    events = discard_distribution.decide(
        state=target,
        command=DiscardDistribution(
            distribution_id=target.id,
            reason="  bytes reclaimed from cold tier  ",
        ),
        context=_context(siblings=(target_result(target), sibling)),
        now=_NOW,
        discarded_by=_DISCARDED_BY,
    )
    assert events == [
        DistributionDiscarded(
            distribution_id=target.id,
            reason="bytes reclaimed from cold tier",
            occurred_at=_NOW,
            discarded_by=_DISCARDED_BY,
        )
    ]


@pytest.mark.unit
def test_decide_raises_last_verified_when_only_same_tier_verified_sibling() -> None:
    """A Verified sibling on the SAME supply_id is not redundancy: the
    bytes-on-a-different-tier invariant is unmet."""
    target = _distribution(distribution_id=uuid4(), supply_id=_SUPPLY_A)
    same_tier = _sibling(distribution_id=uuid4(), supply_id=_SUPPLY_A, status="Verified")
    with pytest.raises(DistributionCannotDiscardLastVerifiedError) as exc_info:
        discard_distribution.decide(
            state=target,
            command=DiscardDistribution(distribution_id=target.id, reason="reclaim"),
            context=_context(siblings=(target_result(target), same_tier)),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )
    assert exc_info.value.distribution_id == target.id
    assert exc_info.value.dataset_id == _DATASET_ID


@pytest.mark.unit
def test_decide_raises_last_verified_when_sibling_only_registered_or_stale() -> None:
    target = _distribution(distribution_id=uuid4(), supply_id=_SUPPLY_A)
    registered = _sibling(distribution_id=uuid4(), supply_id=_SUPPLY_B, status="Registered")
    stale = _sibling(distribution_id=uuid4(), supply_id=_SUPPLY_B, status="Stale")
    with pytest.raises(DistributionCannotDiscardLastVerifiedError):
        discard_distribution.decide(
            state=target,
            command=DiscardDistribution(distribution_id=target.id, reason="reclaim"),
            context=_context(siblings=(target_result(target), registered, stale)),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )


@pytest.mark.unit
def test_decide_raises_last_verified_when_no_sibling_at_all() -> None:
    target = _distribution(distribution_id=uuid4(), supply_id=_SUPPLY_A)
    with pytest.raises(DistributionCannotDiscardLastVerifiedError):
        discard_distribution.decide(
            state=target,
            command=DiscardDistribution(distribution_id=target.id, reason="reclaim"),
            context=_context(siblings=(target_result(target),)),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )


@pytest.mark.unit
def test_decide_emits_when_discarding_a_verified_copy_with_redundant_verified_sibling() -> None:
    """Discarding a Verified copy is allowed when another Verified copy
    rests on a different tier."""
    target = _distribution(
        distribution_id=uuid4(),
        supply_id=_SUPPLY_A,
        status=DistributionStatus.VERIFIED,
    )
    sibling = _sibling(distribution_id=uuid4(), supply_id=_SUPPLY_B, status="Verified")
    events = discard_distribution.decide(
        state=target,
        command=DiscardDistribution(distribution_id=target.id, reason="reclaim"),
        context=_context(siblings=(target_result(target, status="Verified"), sibling)),
        now=_NOW,
        discarded_by=_DISCARDED_BY,
    )
    assert len(events) == 1
    assert isinstance(events[0], DistributionDiscarded)


@pytest.mark.unit
def test_decide_raises_cannot_discard_when_already_discarded() -> None:
    """Strict-not-idempotent: re-discarding an already-Discarded copy raises."""
    target = _distribution(
        distribution_id=uuid4(),
        supply_id=_SUPPLY_A,
        status=DistributionStatus.DISCARDED,
    )
    sibling = _sibling(distribution_id=uuid4(), supply_id=_SUPPLY_B, status="Verified")
    with pytest.raises(DistributionCannotDiscardError) as exc_info:
        discard_distribution.decide(
            state=target,
            command=DiscardDistribution(distribution_id=target.id, reason="second"),
            context=_context(siblings=(sibling,)),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )
    assert exc_info.value.current_status is DistributionStatus.DISCARDED


@pytest.mark.unit
def test_decide_raises_under_discarded_dataset_when_parent_discarded() -> None:
    target = _distribution(distribution_id=uuid4(), supply_id=_SUPPLY_A)
    sibling = _sibling(distribution_id=uuid4(), supply_id=_SUPPLY_B, status="Verified")
    with pytest.raises(DistributionCannotDiscardUnderDiscardedDatasetError) as exc_info:
        discard_distribution.decide(
            state=target,
            command=DiscardDistribution(distribution_id=target.id, reason="reclaim"),
            context=_context(
                siblings=(target_result(target), sibling),
                dataset_status=DatasetStatus.DISCARDED,
            ),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )
    assert exc_info.value.dataset_id == _DATASET_ID


@pytest.mark.unit
def test_decide_raises_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(DistributionNotFoundError) as exc_info:
        discard_distribution.decide(
            state=None,
            command=DiscardDistribution(distribution_id=target_id, reason="X"),
            context=_context(siblings=()),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )
    assert exc_info.value.distribution_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_whitespace_only() -> None:
    target = _distribution(distribution_id=uuid4(), supply_id=_SUPPLY_A)
    sibling = _sibling(distribution_id=uuid4(), supply_id=_SUPPLY_B, status="Verified")
    with pytest.raises(InvalidDistributionDiscardReasonError):
        discard_distribution.decide(
            state=target,
            command=DiscardDistribution(distribution_id=target.id, reason="   "),
            context=_context(siblings=(target_result(target), sibling)),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_too_long() -> None:
    target = _distribution(distribution_id=uuid4(), supply_id=_SUPPLY_A)
    sibling = _sibling(distribution_id=uuid4(), supply_id=_SUPPLY_B, status="Verified")
    with pytest.raises(InvalidDistributionDiscardReasonError):
        discard_distribution.decide(
            state=target,
            command=DiscardDistribution(
                distribution_id=target.id,
                reason="a" * (REASON_MAX_LENGTH + 1),
            ),
            context=_context(siblings=(target_result(target), sibling)),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )


@pytest.mark.unit
def test_decide_validates_reason_before_status_guard() -> None:
    """A whitespace-only reason on an already-Discarded copy raises the
    reason error, not the cannot-discard error. Same precedent as
    discard_dataset / stop_run / truncate_run."""
    target = _distribution(
        distribution_id=uuid4(),
        supply_id=_SUPPLY_A,
        status=DistributionStatus.DISCARDED,
    )
    with pytest.raises(InvalidDistributionDiscardReasonError):
        discard_distribution.decide(
            state=target,
            command=DiscardDistribution(distribution_id=target.id, reason="   "),
            context=_context(siblings=()),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    target = _distribution(distribution_id=uuid4(), supply_id=_SUPPLY_A)
    sibling = _sibling(distribution_id=uuid4(), supply_id=_SUPPLY_B, status="Verified")
    cmd = DiscardDistribution(distribution_id=target.id, reason="reclaim")
    ctx = _context(siblings=(target_result(target), sibling))
    first = discard_distribution.decide(
        state=target, command=cmd, context=ctx, now=_NOW, discarded_by=_DISCARDED_BY
    )
    second = discard_distribution.decide(
        state=target, command=cmd, context=ctx, now=_NOW, discarded_by=_DISCARDED_BY
    )
    assert first == second


def target_result(
    target: Distribution, *, status: str = "Registered"
) -> DatasetDistributionLookupResult:
    """The target copy's own projection row, present in the sibling set
    returned by find_by_datasets (the decider filters it out by id)."""
    return DatasetDistributionLookupResult(
        distribution_id=target.id,
        dataset_id=target.dataset_id,
        supply_id=target.supply_id,
        status=status,
    )
