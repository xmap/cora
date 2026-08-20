"""Unit tests for the `mark_distribution_stale` slice's pure decider.

Unlike `discard_distribution`, marking stale records a fact about the
world that already happened; it is not a deliberate act CORA is
entitled to refuse. The only guard is structural: the target must exist
and must not already be Discarded (terminal). There is no redundancy
guard, no parent-Dataset guard, and no cross-aggregate context.
"""

from dataclasses import fields
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

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
    InvalidDistributionMarkStaleReasonError,
    TriggerSource,
)
from cora.data.features import mark_distribution_stale
from cora.data.features.mark_distribution_stale import MarkDistributionStale
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)
_MARKED_STALE_BY = ActorId(UUID("01900000-0000-7000-8000-000000000099"))
_DATASET_ID = UUID("01900000-0000-7000-8000-0000000000d1")
_SUPPLY_A = UUID("01900000-0000-7000-8000-0000000000a1")


def _distribution(
    *,
    distribution_id: UUID,
    status: DistributionStatus = DistributionStatus.REGISTERED,
) -> Distribution:
    return Distribution(
        id=distribution_id,
        dataset_id=_DATASET_ID,
        supply_id=_SUPPLY_A,
        uri=DistributionUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        access_protocol=AccessProtocol.S3,
        registered_at=_NOW,
        registered_by=_MARKED_STALE_BY,
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_marked_stale_for_a_registered_copy() -> None:
    target = _distribution(distribution_id=uuid4())
    events = mark_distribution_stale.decide(
        state=target,
        command=MarkDistributionStale(
            distribution_id=target.id,
            reason="  storage array declared dead by operations  ",
        ),
        now=_NOW,
        marked_stale_by=_MARKED_STALE_BY,
    )
    assert events == [
        DistributionMarkedStale(
            distribution_id=target.id,
            reason="storage array declared dead by operations",
            trigger=TriggerSource.OPERATOR.value,
            occurred_at=_NOW,
            marked_stale_by=_MARKED_STALE_BY,
        )
    ]


@pytest.mark.unit
def test_decide_stamps_operator_trigger_that_the_caller_cannot_supply() -> None:
    """The trigger is the slice's fact, not the caller's claim. Both
    halves matter: the decider stamps Operator, AND the command carries
    no trigger field for a principal to set, so nobody can assert their
    own report came from a monitor. A reconciliation sweep gets its own
    slice stamping Monitor, mirroring Supply's observe_supply_status."""
    target = _distribution(distribution_id=uuid4())

    events = mark_distribution_stale.decide(
        state=target,
        command=MarkDistributionStale(distribution_id=target.id, reason="array declared dead"),
        now=_NOW,
        marked_stale_by=_MARKED_STALE_BY,
    )

    assert events[0].trigger == TriggerSource.OPERATOR.value
    assert "trigger" not in {f.name for f in fields(MarkDistributionStale)}


@pytest.mark.unit
def test_decide_emits_marked_stale_when_target_is_the_last_verified_copy() -> None:
    """The distinction this slice is built around: marking stale the
    LAST Verified copy of a Dataset succeeds. Unlike discard, there is
    no redundancy guard; if the array died, the array died."""
    target = _distribution(distribution_id=uuid4(), status=DistributionStatus.VERIFIED)
    events = mark_distribution_stale.decide(
        state=target,
        command=MarkDistributionStale(distribution_id=target.id, reason="array failure"),
        now=_NOW,
        marked_stale_by=_MARKED_STALE_BY,
    )
    assert len(events) == 1
    assert isinstance(events[0], DistributionMarkedStale)


@pytest.mark.unit
def test_decide_emits_marked_stale_when_target_is_already_stale() -> None:
    """Re-marking an already-Stale copy succeeds (not strict-not-
    idempotent like discard): a second true report is still recorded."""
    target = _distribution(distribution_id=uuid4(), status=DistributionStatus.STALE)
    events = mark_distribution_stale.decide(
        state=target,
        command=MarkDistributionStale(distribution_id=target.id, reason="confirmed again"),
        now=_NOW,
        marked_stale_by=_MARKED_STALE_BY,
    )
    assert len(events) == 1
    assert isinstance(events[0], DistributionMarkedStale)


@pytest.mark.unit
def test_decide_raises_cannot_mark_stale_when_already_discarded() -> None:
    """Discarded is terminal: a Discarded copy cannot be marked Stale."""
    target = _distribution(distribution_id=uuid4(), status=DistributionStatus.DISCARDED)
    with pytest.raises(DistributionCannotMarkStaleError) as exc_info:
        mark_distribution_stale.decide(
            state=target,
            command=MarkDistributionStale(distribution_id=target.id, reason="too late"),
            now=_NOW,
            marked_stale_by=_MARKED_STALE_BY,
        )
    assert exc_info.value.current_status is DistributionStatus.DISCARDED
    assert exc_info.value.distribution_id == target.id


@pytest.mark.unit
def test_decide_raises_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(DistributionNotFoundError) as exc_info:
        mark_distribution_stale.decide(
            state=None,
            command=MarkDistributionStale(distribution_id=target_id, reason="X"),
            now=_NOW,
            marked_stale_by=_MARKED_STALE_BY,
        )
    assert exc_info.value.distribution_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_whitespace_only() -> None:
    target = _distribution(distribution_id=uuid4())
    with pytest.raises(InvalidDistributionMarkStaleReasonError):
        mark_distribution_stale.decide(
            state=target,
            command=MarkDistributionStale(distribution_id=target.id, reason="   "),
            now=_NOW,
            marked_stale_by=_MARKED_STALE_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_too_long() -> None:
    target = _distribution(distribution_id=uuid4())
    with pytest.raises(InvalidDistributionMarkStaleReasonError):
        mark_distribution_stale.decide(
            state=target,
            command=MarkDistributionStale(
                distribution_id=target.id,
                reason="a" * (REASON_MAX_LENGTH + 1),
            ),
            now=_NOW,
            marked_stale_by=_MARKED_STALE_BY,
        )


@pytest.mark.unit
def test_decide_validates_reason_before_status_guard() -> None:
    """A whitespace-only reason on an already-Discarded copy raises the
    reason error, not the cannot-mark-stale error. Same precedent as
    discard_distribution."""
    target = _distribution(distribution_id=uuid4(), status=DistributionStatus.DISCARDED)
    with pytest.raises(InvalidDistributionMarkStaleReasonError):
        mark_distribution_stale.decide(
            state=target,
            command=MarkDistributionStale(distribution_id=target.id, reason="   "),
            now=_NOW,
            marked_stale_by=_MARKED_STALE_BY,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    target = _distribution(distribution_id=uuid4())
    cmd = MarkDistributionStale(distribution_id=target.id, reason="array failure")
    first = mark_distribution_stale.decide(
        state=target, command=cmd, now=_NOW, marked_stale_by=_MARKED_STALE_BY
    )
    second = mark_distribution_stale.decide(
        state=target, command=cmd, now=_NOW, marked_stale_by=_MARKED_STALE_BY
    )
    assert first == second
